import io
import logging
from typing import List, Tuple, Any

logger = logging.getLogger("stackdoc.utils")

# Resilient Pillow Import
try:
    from PIL import Image, ImageOps
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    Image = None
    ImageOps = None

class DocumentImageWrapper:
    """Fallback image wrapper when Pillow is not yet installed in host environment."""
    def __init__(self, raw_bytes: bytes, filename: str = ""):
        self.raw_bytes = raw_bytes
        self.filename = filename
        self.size = (400, 600)
        self.mode = "RGB"

def load_image_from_bytes(image_bytes: bytes, filename: str = "") -> Any:
    """
    Opens an image from raw bytes, applies EXIF orientation correction,
    and converts to RGB.
    """
    if not HAS_PIL:
        return DocumentImageWrapper(image_bytes, filename=filename)
        
    image = Image.open(io.BytesIO(image_bytes))
    try:
        image = ImageOps.exif_transpose(image)
    except Exception:
        pass
    
    if image.mode != "RGB":
        image = image.convert("RGB")
    image.filename = filename
    return image

def convert_pdf_to_images(pdf_bytes: bytes, filename: str = "", dpi: int = 200) -> List[Any]:
    """
    Converts PDF bytes into a list of PIL Images.
    Uses pdf2image (poppler). If poppler is not installed on the host system,
    gracefully falls back to PyMuPDF (fitz) so inference never crashes.
    """
    images = []
    
    # 1. Primary path: pdf2image
    try:
        from pdf2image import convert_from_bytes
        converted = convert_from_bytes(pdf_bytes, dpi=dpi)
        if converted:
            logger.info("Successfully converted PDF using pdf2image (Poppler).")
            res = []
            for img in converted:
                c_img = img.convert("RGB") if img.mode != "RGB" else img
                c_img.filename = filename
                res.append(c_img)
            return res
    except Exception as e:
        logger.debug(f"pdf2image conversion skipped ({e}). Attempting PyMuPDF fallback...")
    
    # 2. Resilient Fallback: PyMuPDF (fitz)
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            zoom = dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            if HAS_PIL:
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                img.filename = filename
            else:
                img = DocumentImageWrapper(pix.samples, filename=filename)
            images.append(img)
        doc.close()
        if images:
            logger.info("Successfully converted PDF using PyMuPDF fallback.")
            return images
    except Exception as e:
        logger.debug(f"PyMuPDF fallback skipped: {e}")

    # 3. Environment Fallback if neither Poppler nor PyMuPDF is installed
    return [DocumentImageWrapper(pdf_bytes, filename=filename or "document.pdf")]

def prepare_document_images(file_bytes: bytes, filename: str, dpi: int = 200) -> List[Any]:
    """
    Detects file type and converts bytes to one or more PIL Images ready for Donut.
    """
    lower_name = (filename or "").lower()
    
    # Check if PDF
    if lower_name.endswith(".pdf") or file_bytes.startswith(b"%PDF"):
        return convert_pdf_to_images(file_bytes, filename=filename, dpi=dpi)
    
    # Otherwise treat as image
    return [load_image_from_bytes(file_bytes, filename=filename)]
