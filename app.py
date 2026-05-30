import os
import io
import datetime
import gc
from flask import Flask, request, send_file, jsonify, make_response
from flask_cors import CORS
from google.cloud import storage
import pytesseract
from pdf2image import convert_from_path
from pypdf import PdfWriter, PdfReader

app = Flask(__name__)
# Liberação total de CORS para aceitar a origem do Power Pages
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Configuração estável do caminho do binário do Tesseract no Docker Linux
pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'

BUCKET_NAME = "mvp-ocr-arquivos-temporarios"

def obter_client_storage():
    return storage.Client()

@app.route("/api/obter-url-assinada", methods=["POST", "OPTIONS"])
def obter_url_assinada():
    if request.method == "OPTIONS":
        return make_response("", 200)
    try:
        dados = request.json or {}
        nome_arquivo = dados.get("filename", "documento.pdf")
        
        storage_client = obter_client_storage()
        bucket = storage_client.bucket(BUCKET_NAME)
        
        nome_objeto = f"uploads/{int(datetime.datetime.utcnow().timestamp())}_{nome_arquivo}"
        blob = bucket.blob(nome_objeto)
        
        url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(minutes=15),
            method="PUT",
            content_type="application/pdf"
        )
        
        return jsonify({"upload_url": url, "object_name": nome_objeto})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/conversor-ocr", methods=["POST", "OPTIONS"])
def processar_ocr():
    if request.method == "OPTIONS":
        return make_response("", 200)
    try:
        dados = request.json or {}
        nome_objeto = dados.get("object_name")
        idioma_web = dados.get("idioma", "pt")
        # Converte o idioma do select "pt/en" do Pages para o padrão "por/eng" do seu Streamlit
        idioma_ocr = "por" if idioma_web == "pt" or idioma_web == "por" else "eng"
        
        if not nome_objeto:
            return jsonify({"error": "Nome do objeto nao fornecido."}), 400
            
        storage_client = obter_client_storage()
        bucket = storage_client.bucket(BUCKET_NAME)
        blob_input = bucket.blob(nome_objeto)
        
        if not blob_input.exists():
            return jsonify({"error": "Arquivo nao localizado no Storage."}), 404
            
        nome_puro = nome_objeto.split("/")[-1]
        caminho_input = f"/tmp/{nome_puro}"
        
        # Baixa o PDF do bucket temporário direto para o ambiente Linux
        blob_input.download_to_filename(caminho_input)
        
        # --LÓGICA ORIGINAL DO STREAMLIT ADAPTADA PARA PATHS ---
        # Converte o PDF em imagens na resolução estável de 150 DPI para conter a RAM
        images = convert_from_path(caminho_input, dpi=150)
        pdf_writer = PdfWriter()
        
        for img in images:
            # Gera os bytes do PDF com a camada de texto do Tesseract
            page_pdf_bytes = pytesseract.image_to_pdf_or_hocr(img, lang=idioma_ocr, extension='pdf')
            # Anexa a página processada na pilha final
            pdf_writer.add_page(PdfReader(io.BytesIO(page_pdf_bytes)).pages[0])
            del page_pdf_bytes
            
        # Compila o resultado de volta para o fluxo de memória de saída
        out_stream = io.BytesIO()
        pdf_writer.write(out_stream)
        out_stream.seek(0)
        
        # RETENÇÃO ZERO: Limpeza absoluta local de rastro de RAM e disco temporário
        if os.path.exists(caminho_input):
            os.remove(caminho_input)
        try:
            blob_input.delete()
        except Exception:
            pass
            
        del images
        gc.collect()
        
        return send_file(
            out_stream,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"OCR_{nome_puro.split('_', 1)[-1]}"
        )
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=porta)