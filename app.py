import os
import io
import gc
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import pytesseract
from pdf2image import convert_from_bytes
from pypdf import PdfWriter, PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.colors import transparent

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

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
            width, height = img.size
            
            # 1. Obtém os dados detalhados de OCR (palavras e coordenadas em pixels)
            ocr_data = pytesseract.image_to_data(img, lang=idioma_tesseract, output_type=pytesseract.Output.DICT)
            
            # 2. Cria a página com o tamanho exato em pixels para casar 1:1 com as coordenadas do Tesseract
            pdf_buffer = io.BytesIO()
            canv = canvas.Canvas(pdf_buffer, pagesize=(width, height))
            
            # Injeta a imagem ocupando exatamente o tamanho total da página em pixels
            canv.drawInlineImage(img, 0, 0, width=width, height=height)
            
            # 3. Injeta a camada de texto invisível perfeitamente alinhada
            canv.setFillColor(transparent)
            
            n_boxes = len(ocr_data['text'])
            for i in range(n_boxes):
                texto = ocr_data['text'][i].strip()
                if texto: 
                    x = ocr_data['left'][i]
                    y = ocr_data['top'][i]
                    w = ocr_data['width'][i]
                    h = ocr_data['height'][i]
                    
                    # Inversão do eixo Y refletindo a altura real em pixels da imagem
                    y_corrigido = height - y - h
                    
                    # Define o tamanho da fonte com base na altura real da caixa de detecção
                    canv.setFont("Helvetica", max(h, 1))
                    
                    # Define a largura exata que a palavra deve ocupar para evitar sobreposição
                    canv.drawString(x, y_corrigido, texto)
            
            canv.showPage()
            canv.save()
            
            # 4. Lê a página recém-criada e adiciona ao escritor final
            pdf_buffer.seek(0)
            pdf_writer.add_page(PdfReader(pdf_buffer).pages[0])
            
            del pdf_buffer
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