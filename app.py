import os
import io
import subprocess
import gc
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS

app = Flask(__name__)

# Configuração robusta e explícita de CORS para aceitar origens externas e cabeçalhos de formulário
CORS(app, resources={r"/api/*": {
    "origins": "*",
    "methods": ["POST", "OPTIONS"],
    "allow_headers": ["Content-Type", "Authorization"]
}})

@app.route("/api/conversor-ocr", methods=["POST"])
def processar_ocr():
    try:
        if "file" not in request.files:
            return jsonify({"error": "Nenhum arquivo enviado no formulário."}), 400
            
        arquivo = request.files["file"]
        idioma_web = request.form.get("idioma", "pt")
        
        # Mapeia o padrão do select para o padrão de três letras do Tesseract/OCRmyPDF
        idioma_ocr = "por" if idioma_web == "pt" else "eng"
        
        # Caminhos temporários seguros dentro do container Linux (/tmp roda direto na RAM no Cloud Run)
        caminho_input = f"/tmp/input_{arquivo.filename}"
        caminho_output = f"/tmp/output_{arquivo.filename}"
        
        # Salva o arquivo de entrada temporariamente na RAM do container
        arquivo.save(caminho_input)
        
        # Executa o OCRmyPDF via linha de comando de forma síncrona e isolada
        # --skip-text: pula páginas que já possuem texto
        # --optimize 0: desativa compressões pesadas para economizar CPU e RAM no MVP
        comando = [
            "ocrmypdf",
            "-l", idioma_ocr,
            "--skip-text",
            "--optimize", "0",
            caminho_input,
            caminho_output
        ]
        
        # Roda o processo e captura possíveis erros do terminal Linux
        resultado = subprocess.run(comando, capture_output=True, text=True, check=True)
        
        # Lê o PDF processado final diretamente para a memória
        buffer_saida = io.BytesIO()
        with open(caminho_output, "rb") as f:
            buffer_saida.write(f.read())
        buffer_saida.seek(0)
        
        # RETENÇÃO ZERO: Remove os arquivos físicos temporários da RAM imediatamente
        if os.path.exists(caminho_input):
            os.remove(caminho_input)
        if os.path.exists(caminho_output):
            os.remove(caminho_output)
            
        gc.collect()
        
        return send_file(
            buffer_saida,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"OCR_{arquivo.filename}"
        )
        
    except subprocess.CalledProcessError as e:
        return jsonify({"error": f"Erro no motor OCR: {e.stderr}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=porta)