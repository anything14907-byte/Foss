import re
import os
import glob
import logging
from typing import Dict, Any, Optional
from PIL import Image

# Defensive torch import
try:
    import torch
    HAS_TORCH = True
except ImportError:
    torch = None
    HAS_TORCH = False

from backend.config import settings
from backend.postprocessor import postprocess_donut_output

logger = logging.getLogger("stackdoc.model")

def resolve_model_path(model_name: str) -> str:
    """
    Resolves local huggingface snapshot if present to enable offline inference,
    otherwise returns model_name.
    """
    target = model_name.replace("/", "--")
    cache_pattern = os.path.expanduser(f"~/.cache/huggingface/hub/models--{target}/snapshots/*")
    snapshots = sorted(glob.glob(cache_pattern))
    if snapshots and os.path.isdir(snapshots[0]):
        logger.info(f"Using local Hugging Face snapshot: {snapshots[0]}")
        return snapshots[0]
    return model_name

class DonutDocumentParser:
    """
    Layout-Aware Document Understanding Engine using Donut
    (Document Understanding Transformer via Hugging Face).
    Processes visual document layout directly into structured JSON
    without any OCR pipeline or bounding box pre-computation.
    """
    def __init__(self):
        self.device = torch.device(settings.DEVICE) if (HAS_TORCH and torch is not None) else "cpu"
        self.model_name = settings.MODEL_NAME
        self.task_prompt = settings.TASK_PROMPT
        self.processor = None
        self.model = None
        self.is_loaded = False
        self._load_error: Optional[str] = None
        
    def load_model(self) -> None:
        """
        Loads the Donut processor and VisionEncoderDecoderModel from Hugging Face or local cache.
        """
        if self.is_loaded:
            return

        if not HAS_TORCH:
            self._load_error = "PyTorch is not installed in the environment."
            logger.error(self._load_error)
            return

        resolved_path = resolve_model_path(self.model_name)
        logger.info(f"Loading Donut model from '{resolved_path}' on device '{self.device}'...")
        try:
            from transformers import DonutProcessor, VisionEncoderDecoderModel
            
            # Load processor
            self.processor = DonutProcessor.from_pretrained(resolved_path)
            
            # Load model (fall back to PyTorch bin if safetensors not in snapshot)
            try:
                self.model = VisionEncoderDecoderModel.from_pretrained(resolved_path)
            except Exception:
                self.model = VisionEncoderDecoderModel.from_pretrained(resolved_path, use_safetensors=False)

            # Ensure vocab_size is accessible on root config for compute_transition_scores
            if not hasattr(self.model.config, "vocab_size") and hasattr(self.model.config, "decoder"):
                self.model.config.vocab_size = self.model.config.decoder.vocab_size

            self.model.to(self.device)
            self.model.eval()
            self.is_loaded = True
            self._load_error = None
            logger.info("Donut model loaded successfully into memory.")
        except Exception as e:
            self.is_loaded = False
            self.model = None
            self.processor = None
            self._load_error = str(e)
            logger.error(f"Failed to load Donut model: {e}")

    def parse_image(self, image: Any) -> Dict[str, Any]:
        """
        Takes an image of an invoice/receipt and predicts structured key-value pairs
        using the real Donut Vision-Language Transformer.
        Never returns fabricated data.
        """
        if not self.is_loaded:
            self.load_model()

        if not self.is_loaded or self.model is None or self.processor is None:
            raise RuntimeError(
                f"Donut model is not loaded: {self._load_error or 'Weights unavailable'}. "
                "Ensure weights are cached or run scripts/download_model.py."
            )

        return self._predict_neural(image)

    def _predict_neural(self, image: Any) -> Dict[str, Any]:
        """
        Runs real neural inference with the Donut transformer and computes honest confidence.
        """
        # 1. Prepare image tensor using Donut processor
        pixel_values = self.processor(image, return_tensors="pt").pixel_values
        pixel_values = pixel_values.to(self.device)

        # 2. Prepare task decoder prompt (<s_cord-v2>)
        decoder_input_ids = self.processor.tokenizer(
            self.task_prompt,
            add_special_tokens=False,
            return_tensors="pt"
        ).input_ids.to(self.device)

        # 3. Autoregressive layout-aware generation
        with torch.no_grad():
            outputs = self.model.generate(
                pixel_values,
                decoder_input_ids=decoder_input_ids,
                max_length=settings.MAX_LENGTH,
                early_stopping=True,
                pad_token_id=self.processor.tokenizer.pad_token_id,
                eos_token_id=self.processor.tokenizer.eos_token_id,
                use_cache=True,
                num_beams=1,
                bad_words_ids=[[self.processor.tokenizer.unk_token_id]],
                return_dict_in_generate=True,
                output_scores=True,
            )

        # 4. Compute real token confidence using transition scores
        real_confidence: Optional[float] = None
        try:
            if hasattr(self.model, "compute_transition_scores") and outputs.scores:
                transition_scores = self.model.compute_transition_scores(
                    outputs.sequences, outputs.scores, normalize_logits=True
                )
                token_probs = torch.exp(transition_scores)
                if token_probs.numel() > 0:
                    raw_val = float(token_probs.mean().item())
                    real_confidence = max(0.0, min(1.0, round(raw_val, 4)))
        except Exception as e:
            logger.warning(f"Could not compute transition scores confidence: {e}")
            real_confidence = None

        # 5. Decode sequence tokens
        seq = self.processor.batch_decode(outputs.sequences)[0]
        seq = seq.replace(self.processor.tokenizer.eos_token, "").replace(self.processor.tokenizer.pad_token, "")
        # Remove any trailing unclosed XML tag at the very end of sequence
        seq = re.sub(r"<[^>]*$", "", seq).strip()

        # 6. Convert tokens to JSON via processor or fallback XML regex
        try:
            raw_json = self.processor.token2json(seq)
        except Exception as e:
            logger.warning(f"token2json parsing exception: {e}")
            raw_json = None

        # 7. Post-process into standardized schema with real confidence
        result = postprocess_donut_output(
            donut_output=raw_json if raw_json is not None else seq,
            raw_sequence=seq,
            confidence=real_confidence
        )
        result["engine"] = "donut"
        result["device"] = str(self.device)
        return result

# Singleton instance
donut_engine = DonutDocumentParser()
