import os
import io
import time
import json
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from google.cloud import vision
from google.cloud import storage

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Inicializa os clientes oficiais do Google usando o IAM do Cloud Run
vision_client = vision.ImageAnnotatorClient()
storage_client = storage.Client()

BUCKET_NAME = "mvp-ocr-arquivos-temporarios"

@app.route("/api/conversor-ocr", methods=["POST"])
def processar_ocr():
    blob_entrada = None
    blob_saida = None
    try:
        if "file" not in request.files:
            return jsonify({"error": "Nenhum arquivo enviado."}), 400
            
        arquivo = request.files["file"]
        idioma = request.form.get("idioma", "pt")
        
        bucket = storage_client.bucket(BUCKET_NAME)
        timestamp = int(time.time())
        
        # 1. Upload do PDF original para o GCS (Fase Temporária)
        nome_arquivo_in = f"input_{timestamp}_{arquivo.filename}"
        blob_entrada = bucket.blob(nome_arquivo_in)
        blob_entrada.upload_from_file(arquivo.stream, content_type="application/pdf")
        
        gcs_source_uri = f"gs://{BUCKET_NAME}/{nome_arquivo_in}"
        gcs_destination_uri = f"gs://{BUCKET_NAME}/output_{timestamp}/"
        
        # 2. Configura o motor de IA do Google Vision para gerar um PDF Pesquisável
        gcs_source = vision.GcsSource(uri=gcs_source_uri)
        input_config = vision.InputConfig(gcs_source=gcs_source, mime_type="application/pdf")
        
        gcs_destination = vision.GcsDestination(uri=gcs_destination_uri)
        output_config = vision.OutputConfig(gcs_destination=gcs_destination, batch_size=100)
        
        feature = vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)
        
        solicitacao = vision.AsyncAnnotateFileRequest(
            features=[feature],
            input_config=input_config,
            output_config=output_config,
            image_context=vision.ImageContext(language_hints=[idioma])
        )
        
        # 3. Dispara a operação assíncrona oficial do Google Cloud
        operacao = vision_client.async_batch_annotate_files(requests=[solicitacao])
        operacao.result(timeout=180) # Aguarda o motor do Google processar o documento
        
        # 4. Localiza o PDF Pesquisável gerado pelo Google dentro do Bucket
        prefixo_saida = f"output_{timestamp}/"
        blobs = list(bucket.list_blobs(prefix=prefixo_saida))
        
        # O Google Cloud Vision gera o PDF processado com o sufixo output-page-X-to-Y.pdf
        pdf_processado_blob = next((b for b in blobs if b.name.endswith(".pdf")), None)
        
        if not pdf_processado_blob:
            return jsonify({"error": "O motor do Google falhou em reconstruir o PDF."}), 500
            
        # Baixa o arquivo final renderizado pelo Google para a memória RAM
        buffer_saida = io.BytesIO()
        pdf_processado_blob.download_to_file(buffer_saida)
        buffer_saida.seek(0)
        
        # 5. RETENÇÃO ZERO: Limpeza absoluta dos arquivos temporários no Bucket
        try:
            blob_entrada.delete()
            for b in blobs:
                b.delete()
        except Exception as e:
            print(f"Aviso de limpeza de rastro: {e}")
            
        return send_file(
            buffer_saida,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"OCR_{arquivo.filename}"
        )
        
    except Exception as e:
        # Garante a limpeza em caso de falha no meio do processo
        if blob_entrada and blob_entrada.exists():
            blob_entrada.delete()
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=porta)