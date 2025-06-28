import io, fitz, docx, base64
from PIL import Image

def pdf_to_text(file_bytes: bytes) -> str:
    pdf = fitz.open(stream=file_bytes, filetype="pdf")
    return "".join(page.get_text() for page in pdf)

def docx_to_text(file_bytes: bytes) -> str:
    buf = io.BytesIO(file_bytes)
    doc = docx.Document(buf)
    return "\n".join(p.text for p in doc.paragraphs)

def image_to_base64(file_bytes: bytes) -> str:
    img = Image.open(io.BytesIO(file_bytes))
    with io.BytesIO() as out:
        img.save(out, format="PNG")
        return base64.b64encode(out.getvalue()).decode()

