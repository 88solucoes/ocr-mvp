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
        if "file" not in request.files:
            return jsonify({"error": "Nenhum arquivo enviado no formulário."}), 400
            
        arquivo = request.files["file"]
        idioma_web = request.form.get("idioma", "pt")
        idioma_tesseract = "por" if idioma_web == "pt" else "eng"
        
        # 1. Leitura do binário e isolamento das páginas em imagens
        file_bytes = arquivo.read()
        images = convert_from_bytes(file_bytes, res=150)
        
        # Cria leitores para aplicar o merge página por página com o original
        pdf_original = PdfReader(io.BytesIO(file_bytes))
        pdf_writer = PdfWriter()
        
        # 2. Varredura e criação da máscara de texto superior
        for i, img in enumerate(images):
            width, height = img.size
            
            # Obtém os dados detalhados de OCR do Tesseract (coordenadas em pixels)
            ocr_data = pytesseract.image_to_data(img, lang=idioma_tesseract, output_type=pytesseract.Output.DICT)
            
            # Cria um PDF temporário na memória contendo APENAS o texto
            text_pdf_buffer = io.BytesIO()
            canv = canvas.Canvas(text_pdf_buffer, pagesize=(width, height))
            
            # Tornamos o texto invisível usando o modo de renderização de texto do PDF (3 = Invisível)
            # Isso é mais seguro e compatível do que usar cores transparentes estruturais
            canv._code.append("3 Tr") 
            
            n_boxes = len(ocr_data['text'])
            for j in range(n_boxes):
                texto = ocr_data['text'][j].strip()
                if texto: 
                    x = ocr_data['left'][j]
                    y = ocr_data['top'][j]
                    w = ocr_data['width'][j]
                    h = ocr_data['height'][j]
                    
                    # Correção matemática do eixo Y (Inversão Superior -> Inferior)
                    y_corrigido = height - y - h
                    
                    # Desenha o caractere invisível no tamanho real detectado
                    canv.setFont("Helvetica", max(h, 1))
                    canv.drawString(x, y_corrigido, texto)
            
            canv.showPage()
            canv.save()
            text_pdf_buffer.seek(0)
            
            # 3. Engenharia de Fusão (Merge): Joga o texto exatamente por CIMA da imagem original
            page_original = pdf_original.pages[i]
            page_texto = PdfReader(text_pdf_buffer).pages[0]
            
            # Modifica a página original aplicando a camada de texto por cima dela
            page_original.merge_page(page_texto)
            pdf_writer.add_page(page_original)
            
            del text_pdf_buffer
            gc.collect()
            
        # 4. Compilação final do Buffer Volátil de Saída
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