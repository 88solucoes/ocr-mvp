import os
import io
import gc
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import pytesseract
from pdf2image import convert_from_bytes
from pypdf import PdfWriter, PdfReader

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Configuração do caminho do binário do Tesseract dentro do container Linux do Cloud Run
pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'

@app.route("/api/conversor-ocr", methods=["POST"])
def processar_ocr():
    try:
        if "file" not in request.files:
            return jsonify({"error": "Nenhum arquivo enviado no formulário."}), 400
            
        arquivo = request.files["file"]
        idioma_web = request.form.get("idioma", "pt")
        idioma_tesseract = "por" if idioma_web == "pt" else "eng"
        
        file_bytes = arquivo.read()
        images = convert_from_bytes(file_bytes, res=150)
        pdf_writer = PdfWriter()
        
        for img in images:
            page_pdf_bytes = pytesseract.image_to_pdf_or_hocr(img, lang=idioma_tesseract, extension='pdf')
            pdf_writer.add_page(PdfReader(io.BytesIO(page_pdf_bytes)).pages[0])
            del page_pdf_bytes
            
        out_stream = io.BytesIO()
        pdf_writer.write(out_stream)
        out_stream.seek(0)
        
        del images
        gc.collect()
        
        return send_file(
            out_stream,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"OCR_{arquivo.filename}"
        )
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=porta)