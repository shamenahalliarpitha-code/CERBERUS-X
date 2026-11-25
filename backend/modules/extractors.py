from pathlib import Path
import io
import fitz
import pandas as pd
from docx import Document
from PIL import Image

def extract_file(filename: str, content: bytes) -> tuple[str, list[str]]:
    ext = Path(filename).suffix.lower()
    notes = []
    if ext == ".pdf":
        doc = fitz.open(stream=content, filetype="pdf")
        pages = []
        for i, page in enumerate(doc):
            text = page.get_text("text").strip()
            if not text:
                notes.append(f"Page {i+1} appears scanned; OCR is not enabled automatically.")
            if text:
                pages.append(f"[Page {i+1}]\n{text}")
        return "\n\n".join(pages), notes
    if ext == ".docx":
        doc = Document(io.BytesIO(content))
        parts = [p.text for p in doc.paragraphs if p.text.strip()]
        for table_index, table in enumerate(doc.tables, 1):
            for row in table.rows:
                parts.append(" | ".join(cell.text.strip() for cell in row.cells))
        return "\n".join(parts), notes
    if ext in (".xlsx", ".xls", ".csv"):
        if ext == ".csv":
            df = pd.read_csv(io.BytesIO(content)).fillna("")
            sheet_text = df.to_string(index=False)
        else:
            book = pd.ExcelFile(io.BytesIO(content))
            sections = []
            for sheet in book.sheet_names:
                df = pd.read_excel(book, sheet_name=sheet).fillna("")
                sections.append(f"[Sheet: {sheet}]\n{df.to_string(index=False)}")
            sheet_text = "\n\n".join(sections)
        return sheet_text, notes
    if ext in (".txt", ".md"):
        return content.decode("utf-8", errors="replace"), notes
    if ext in (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"):
        try:
            import pytesseract
            image = Image.open(io.BytesIO(content))
            try:
                text = pytesseract.image_to_string(image)
                if text.strip():
                    return text, notes
                notes.append("No readable text detected in image.")
                return "", notes
            except Exception:
                notes.append("Tesseract OCR is installed as a Python package, but the Tesseract application was not found. Install it to enable image OCR.")
                return "", notes
        except Exception as exc:
            notes.append(f"Image OCR unavailable: {exc}")
            return "", notes
    raise ValueError(f"Unsupported file type: {ext}")
