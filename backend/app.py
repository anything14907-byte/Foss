import os
import json
import time
import logging
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.utils import prepare_document_images
from backend.model import donut_engine
from backend.layout_extractor import layout_extractor, count_pdf_words

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("stackdoc.app")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Layout-Aware Document Understanding API built with Donut VLM & PyMuPDF Layout Engine. Sponsored by Build with Stack."
)

# Enable CORS for Chrome Extension and local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CACHED_OUTPUTS_FILE = "data/eval/cached_outputs.json"

@app.on_event("startup")
async def startup_event():
    logger.info("Initializing StackDoc API...")
    logger.info(f"Target Vision-Language Model: {settings.MODEL_NAME}")
    logger.info(f"Compute Device: {settings.DEVICE}")
    logger.info(f"Demo Mode (STACKDOC_DEMO_MODE): {os.getenv('STACKDOC_DEMO_MODE', '0')}")
    # Pre-warm Donut in background
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
        "demo_mode": os.getenv("STACKDOC_DEMO_MODE", "0") == "1",
        "endpoints": {
            "parse_document": "POST /parse-document?mode=auto|donut|layout",
            "health": "GET /health"
        }
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "model_loaded": donut_engine.is_loaded,
        "device": settings.DEVICE,
        "demo_mode": os.getenv("STACKDOC_DEMO_MODE", "0") == "1",
        "sponsor": settings.SPONSOR
    }

@app.post("/parse-document")
async def parse_document(
    request: Request,
    file: UploadFile = File(..., description="PDF or image document file (PNG, JPG, PDF)"),
    page_number: int = Form(1, description="Page number to parse if multi-page PDF (1-indexed)"),
    mode: str = Query("auto", regex="^(auto|donut|layout)$", description="Engine mode: auto, donut, or layout")
):
    """
    Parses an uploaded PDF or image using Layout-Aware extraction.
    Modes:
      - auto: Uses layout extractor for digital PDFs (>20 words); converts to image and uses Donut for scanned receipts/images.
      - donut: Always uses Donut Vision-Language Transformer.
      - layout: Uses coordinate-based layout extractor (digital PDFs only).
    """
    start_time = time.perf_counter()
    stack_project_id = request.headers.get("x-stack-project-id", settings.STACK_PROJECT_ID)
    demo_mode_active = os.getenv("STACKDOC_DEMO_MODE", "0") == "1"

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

    # Check Demo Mode cache
    if demo_mode_active and os.path.exists(CACHED_OUTPUTS_FILE):
        try:
            with open(CACHED_OUTPUTS_FILE, "r") as f:
                cached_data = json.load(f)
            if file.filename in cached_data:
                latency = round(time.perf_counter() - start_time, 4)
                cached_res = cached_data[file.filename]
                return JSONResponse(content={
                    **cached_res,
                    "filename": file.filename,
                    "latency_seconds": latency,
                    "execution_time_seconds": latency,
                    "demo_cached": True,
                    "stack_project_id": stack_project_id,
                    "sponsor": settings.SPONSOR
                })
        except Exception as e:
            logger.warning(f"Demo cache lookup failed: {e}")

    filename_lower = file.filename.lower()
    is_pdf = filename_lower.endswith(".pdf") or contents.startswith(b"%PDF")
    
    parsed_result = None
    warning_message = None

    # Determine processing strategy
    if mode == "layout":
        if not is_pdf:
            raise HTTPException(
                status_code=400,
                detail="Mode 'layout' requires a digital PDF document. For images, use mode=donut or mode=auto."
            )
        try:
            parsed_result = layout_extractor.extract_document(contents)
        except Exception as e:
            logger.error(f"Layout extraction failed: {e}")
            raise HTTPException(status_code=500, detail=f"Layout extractor error: {str(e)}")

    elif mode == "auto" and is_pdf:
        # Check if PDF contains extractable digital words (> 20 words)
        words_count = count_pdf_words(contents)
        if words_count > 20:
            try:
                parsed_result = layout_extractor.extract_document(contents)
            except Exception as e:
                logger.warning(f"Layout engine failed on digital PDF ({e}). Falling back to Donut VLM.")
                warning_message = f"Layout extractor error ({str(e)}). Fell back to Donut VLM."

    # If not yet handled by layout engine, run Donut VLM
    if parsed_result is None:
        try:
            images = prepare_document_images(contents, file.filename, dpi=settings.PDF_DPI)
        except Exception as e:
            logger.error(f"Error preparing document images: {e}")
            raise HTTPException(status_code=422, detail=f"Document image preparation error: {str(e)}")

        if not images:
            raise HTTPException(status_code=422, detail="No valid pages could be extracted from document.")

        target_idx = max(0, min(page_number - 1, len(images) - 1))
        target_image = images[target_idx]

        # Check model loaded
        if not donut_engine.is_loaded:
            try:
                donut_engine.load_model()
            except Exception:
                pass

        if not donut_engine.is_loaded:
            raise HTTPException(
                status_code=503,
                detail="Donut model weights are not loaded. Ensure weights are cached locally or run scripts/download_model.py."
            )

        try:
            parsed_result = donut_engine.parse_image(target_image)
        except Exception as e:
            logger.error(f"Donut model inference failed: {e}")
            raise HTTPException(status_code=500, detail=f"Donut inference failed: {str(e)}")

    latency = round(time.perf_counter() - start_time, 4)

    response_payload = {
        **parsed_result,
        "filename": file.filename,
        "latency_seconds": latency,
        "execution_time_seconds": latency,
        "demo_cached": False,
        "stack_project_id": stack_project_id,
        "sponsor": settings.SPONSOR,
        "repo_url": settings.REPO_URL
    }

    if warning_message:
        response_payload["warning"] = warning_message

    return JSONResponse(content=response_payload)
