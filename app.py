import os
import io
import gc
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import pytesseract
from pdf2image import convert_from_bytes
from pypdf import PdfWriter, PdfReader
from reportlab.pdfgen import canvas

app = Flask(__name__)
# Libera o CORS para a integração segura com o portal do Power Pages
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Configuração estável do caminho do binário do Tesseract no Cloud Run
pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'

@app.route("/api/conversor-ocr", methods=["POST"])
def processar_ocr():
    try:
        # Substitui o 'uploaded_files' do Streamlit pelo payload do formulário HTTP
        file = request.files['file']
        idioma = request.form.get('idioma', 'por')
        
        # Sua lógica exata de processamento de bytes e RAM:
        file_bytes = file.read()
        images = convert_from_bytes(file_bytes, 150)
        pdf_writer = PdfWriter()
        
        for img in images:
            page_pdf_bytes = pytesseract.image_to_pdf_or_hocr(img, lang=idioma, extension='pdf')
            pdf_writer.add_page(PdfReader(io.BytesIO(page_pdf_bytes)).pages[0])
            del page_pdf_bytes
        
        out_stream = io.BytesIO()
        pdf_writer.write(out_stream)
        out_stream.seek(0)
        
        # Gestão de Memória idêntica à sua estrutura anterior
        del images
        gc.collect() 
        
        # Em vez de salvar no st.session_state, cospe o arquivo direto para o usuário baixar
        return send_file(
            out_stream, 
            mimetype="application/pdf", 
            as_attachment=True, 
            download_name=f"OCR_{file.filename}"
        )
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=porta)