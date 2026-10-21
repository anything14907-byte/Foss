#!/usr/bin/env python3
"""
Pre-downloads the Donut model weights and processor from Hugging Face
so inferences can run completely offline during the hackathon demo.
"""
import sys
import logging
from transformers import DonutProcessor, VisionEncoderDecoderModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s]: %(message)s")
logger = logging.getLogger("download_model")

MODEL_NAME = "naver-clova-ix/donut-base-finetuned-cord-v2"

def main():
    logger.info(f"Pre-downloading Donut model: '{MODEL_NAME}'...")
    logger.info("This caches weights locally to guarantee 100% offline hackathon execution.")
    
    try:
        logger.info("Step 1/2: Downloading Processor & Tokenizer...")
        processor = DonutProcessor.from_pretrained(MODEL_NAME)
        logger.info("Processor cached successfully.")
        
        logger.info("Step 2/2: Downloading VisionEncoderDecoderModel weights (~800MB)...")
        model = VisionEncoderDecoderModel.from_pretrained(MODEL_NAME)
        logger.info("Model weights cached successfully.")
        
        print("\n" + "="*60)
        print(" SUCCESS: Donut Model is fully cached locally!")
        print(f" Model: {MODEL_NAME}")
        print(" You can now run the backend without active internet access.")
        print("="*60 + "\n")
    except Exception as e:
        logger.error(f"Failed to download model weights: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
