import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io

def extract_text_from_pdf(path, min_len=40):
    """Extracts clean text from both normal and scanned PDFs."""
    doc = fitz.open(path)
    full_text = ""
    for i, page in enumerate(doc):
        try:
            txt = page.get_text("text")
            full_text += txt + "\n\n"
        except Exception:
            pix = page.get_pixmap()
            img = Image.open(io.BytesIO(pix.tobytes()))
            ocr_text = pytesseract.image_to_string(img)
            full_text += ocr_text + "\n\n"
    chunks = [c.strip() for c in full_text.split("\n\n") if len(c.strip()) >= min_len]
    return chunks
print("✅ reader.py loaded successfully")
