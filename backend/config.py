import os

# Resilient torch detection
try:
    import torch
    DEVICE_DEFAULT = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
except ImportError:
    torch = None
    DEVICE_DEFAULT = "cpu"

# Resilient pydantic / settings detection
try:
    from pydantic_settings import BaseSettings
    class Settings(BaseSettings):
        APP_NAME: str = "StackDoc Layout-Aware Document Understanding"
        APP_VERSION: str = "1.0.0"
        SPONSOR: str = "Build with Stack"
        REPO_URL: str = "https://github.com/anything14907-byte"
        
        # naver-clova-ix/donut-base-finetuned-cord-v2 reads receipts directly without OCR
        MODEL_NAME: str = os.getenv("DONUT_MODEL_NAME", "naver-clova-ix/donut-base-finetuned-cord-v2")
        TASK_PROMPT: str = "<s_cord-v2>"
        MAX_LENGTH: int = 768
        
        DEVICE: str = os.getenv("DEVICE", DEVICE_DEFAULT)
        HOST: str = os.getenv("HOST", "0.0.0.0")
        PORT: int = int(os.getenv("PORT", "8000"))
        
        STACK_PROJECT_ID: str = os.getenv("STACK_PROJECT_ID", "stack-hackathon-foss-forge")
        STACK_AUTH_ENABLED: bool = os.getenv("STACK_AUTH_ENABLED", "false").lower() == "true"
        PDF_DPI: int = 200

        class Config:
            env_file = ".env"
            extra = "ignore"

    settings = Settings()

except ImportError:
    # Lightweight fallback settings if pydantic is not yet installed
    class FallbackSettings:
        APP_NAME: str = "StackDoc Layout-Aware Document Understanding"
        APP_VERSION: str = "1.0.0"
        SPONSOR: str = "Build with Stack"
        REPO_URL: str = "https://github.com/anything14907-byte"
        MODEL_NAME: str = os.getenv("DONUT_MODEL_NAME", "naver-clova-ix/donut-base-finetuned-cord-v2")
        TASK_PROMPT: str = "<s_cord-v2>"
        MAX_LENGTH: int = 768
        DEVICE: str = os.getenv("DEVICE", DEVICE_DEFAULT)
        HOST: str = os.getenv("HOST", "0.0.0.0")
        PORT: int = int(os.getenv("PORT", "8000"))
        STACK_PROJECT_ID: str = os.getenv("STACK_PROJECT_ID", "stack-hackathon-foss-forge")
        STACK_AUTH_ENABLED: bool = False
        PDF_DPI: int = 200

    settings = FallbackSettings()
