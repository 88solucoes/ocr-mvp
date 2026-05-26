import os
import io
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from google.cloud import vision

app = Flask(__name__)
# Libera o CORS para que o domínio do Power Pages (slsfhub.powerappsportals.com) consiga fazer o fetch
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Inicializa o cliente do Google Vision (ele busca as credenciais do ambiente automaticamente)
client = vision.ImageAnnotatorClient()

@app.route("/api/conversor-ocr", methods=["POST"])
def processar_ocr():
    try:
        if "file" not in request.files:
            return jsonify({"error": "Nenhum arquivo enviado no formulário."}), 400
            
        arquivo = request.files["file"]
        idioma = request.form.get("idioma", "pt")
        
        # Leitura do binário direto para a memória RAM (Retenção Zero)
        pdf_bytes = arquivo.read()
        
        # Configura a requisição estruturada para o arquivo PDF completo
        input_config = vision.InputConfig(content=pdf_bytes, mime_type="application/pdf")
        feature = vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)
        
        # Monta a chamada para o container da Vision API
        solicitacao = vision.AnnotateFileRequest(
            input_config=input_config, 
            features=[feature],
            image_context=vision.ImageContext(language_hints=[idioma])
        )
        
        # Dispara o processamento síncrono no Google Cloud
        resposta = client.batch_annotate_files(requests=[solicitacao])
        
        # --- LOGICA DE RESPOSTA ---
        # Aqui a Vision API devolve o JSON com as coordenadas do texto mapeado de cada página.
        # Para fins de teste e validação do fluxo do download no card da direita,
        # vamos devolver o próprio arquivo limpo ou processado em um buffer volátil.
        
        buffer_saida = io.BytesIO(pdf_bytes)
        buffer_saida.seek(0)
        
        return send_file(
            buffer_saida,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"OCR_{arquivo.filename}"
        )
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # O Cloud Run exige que o container escute a porta definida pela variável de ambiente PORT
    porta = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=porta)

# TESTE CI/CD 