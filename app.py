import os
import io
import subprocess
import gc
from flask import Flask, request, send_file, jsonify, make_response
from flask_cors import CORS

app = Flask(__name__)
# Liberação global preventiva
CORS(app, resources={r"/api/*": {"origins": "*"}})

@app.route("/api/conversor-ocr", methods=["POST"])
def processar_ocr():
    try:
        if "file" not in request.files:
            response = jsonify({"error": "Nenhum arquivo enviado no formulário."})
            return make_response(response, 400)
            
        arquivo = request.files["file"]
        idioma_web = request.form.get("idioma", "pt")
        idioma_ocr = "por" if idioma_web == "pt" else "eng"
        
        caminho_input = f"/tmp/input_{arquivo.filename}"
        caminho_output = f"/tmp/output_{arquivo.filename}"
        
        arquivo.save(caminho_input)
        
        # Execução síncrona otimizada local
        comando = [
            "ocrmypdf",
            "-l", idioma_ocr,
            "--skip-text",
            "--optimize", "0",
            caminho_input,
            caminho_output
        ]
        
        subprocess.run(comando, capture_output=True, text=True, check=True)
        
        buffer_saida = io.BytesIO()
        with open(caminho_output, "rb") as f:
            buffer_saida.write(f.read())
        buffer_saida.seek(0)
        
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
        # Envelopa o erro garantindo que o cabeçalho CORS saia na resposta
        response = jsonify({"error": f"Erro no motor OCR: {e.stderr}"})
        return make_response(response, 500)
    except Exception as e:
        response = jsonify({"error": str(e)})
        return make_response(response, 500)

if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=porta)