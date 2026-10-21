import time
import logging
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.utils import prepare_document_images
from backend.model import donut_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("stackdoc.app")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Layout-Aware Document Understanding API built with Donut & Build with Stack."
)

# Enable CORS for Chrome Extension and local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins including chrome-extension://
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    logger.info("Initializing StackDoc API...")
    logger.info(f"Target Vision-Language Model: {settings.MODEL_NAME}")
    logger.info(f"Compute Device: {settings.DEVICE}")
    logger.info(f"Sponsored by: {settings.SPONSOR}")
    logger.info(f"Repository: {settings.REPO_URL}")
    # Pre-warm model in background
    try:
        donut_engine.load_model()
    except Exception as e:
        logger.warning(f"Background model pre-warm deferred: {e}")

@app.get("/")
async def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "sponsor": settings.SPONSOR,
        "sponsor_badge": "Proudly built with Stack (https://buildwithstack.com)",
        "repository": settings.REPO_URL,
        "status": "online",
        "device": settings.DEVICE,
        "model": settings.MODEL_NAME,
        "endpoints": {
            "parse_document": "POST /parse-document",
            "health": "GET /health"
        }
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "model_loaded": donut_engine.is_loaded,
        "device": settings.DEVICE,
        "sponsor": settings.SPONSOR
    }

@app.post("/parse-document")
async def parse_document(
    request: Request,
    file: UploadFile = File(..., description="PDF or image document file (PNG, JPG, PDF)"),
    page_number: int = Form(1, description="Page number to parse if multi-page PDF (1-indexed)")
):
    """
    Parses an uploaded PDF or image using the Donut Layout-Aware Transformer.
    Directly extracts structured invoice/receipt data (Vendor Name, Date, Total Amount, Line Items)
    without plain-text OCR or bounding-box generation.
    """
    start_time = time.time()
    stack_project_id = request.headers.get("x-stack-project-id", settings.STACK_PROJECT_ID)

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded.")

    # Read uploaded bytes
    try:
        contents = await file.read()
        if len(contents) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    except Exception as e:
        logger.error(f"Error reading uploaded file: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

    # Convert to image(s) using layout utilities (pdf2image with PyMuPDF fallback)
    try:
        images = prepare_document_images(contents, file.filename, dpi=settings.PDF_DPI)
    except Exception as e:
        logger.error(f"Error preparing document images: {e}")
        raise HTTPException(status_code=422, detail=f"Document parsing error: {str(e)}")

    if not images:
        raise HTTPException(status_code=422, detail="No valid pages could be extracted from document.")

    # Select page to parse
    target_idx = max(0, min(page_number - 1, len(images) - 1))
    target_image = images[target_idx]

    logger.info(
        f"Processing document '{file.filename}' (Page {target_idx + 1}/{len(images)}) "
        f"- Resolution: {target_image.width}x{target_image.height}"
    )

    # Run inference with Donut
    try:
        parsed_result = donut_engine.parse_image(target_image)
    except Exception as e:
        logger.error(f"Inference failure: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Model inference failed: {str(e)}")

    elapsed = round(time.time() - start_time, 3)

    response_payload = {
        **parsed_result,
        "filename": file.filename,
        "page_processed": target_idx + 1,
        "total_pages": len(images),
        "execution_time_seconds": elapsed,
        "stack_project_id": stack_project_id,
        "sponsor": settings.SPONSOR,
        "repo_url": settings.REPO_URL
    }

    return JSONResponse(content=response_payload)
