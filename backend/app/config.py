from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """Application configuration settings."""
    
    # App settings
    APP_NAME: str = "P&ID Digitization Tool"
    DEBUG: bool = True
    
    # Authentication
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours
    
    # Default admin user (for MVP)
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"
    
    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    STORAGE_DIR: Path = BASE_DIR / "storage"
    DOCUMENTS_DIR: Path = STORAGE_DIR / "documents"
    RENDERED_DIR: Path = STORAGE_DIR / "rendered"
    SYMBOLS_DIR: Path = STORAGE_DIR / "symbols"
    MODELS_DIR: Path = BASE_DIR / "models"
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./pid_digitizer.db"
    
    # PDF Processing
    PDF_DPI: int = 200  # Resolution for PDF to image conversion
    
    class Config:
        env_file = ".env"


settings = Settings()

# Ensure directories exist
for dir_path in [settings.DOCUMENTS_DIR, settings.RENDERED_DIR, settings.SYMBOLS_DIR, settings.MODELS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)
