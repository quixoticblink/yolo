from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .config import settings
from .database import init_db, async_session
from .auth import create_default_admin
from .routers import auth, documents, annotations, symbols, export, inference


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    print(f"Starting {settings.APP_NAME}...")
    await init_db()
    
    # Create default admin user
    async with async_session() as db:
        await create_default_admin(db)
    
    # Preload AI models in background to avoid timeout on first request
    import asyncio
    from services.yolo_detector import get_aws_models
    
    def load_models():
        print("Starting background model loading...")
        try:
            get_aws_models()
            print("Background model loading complete!")
        except Exception as e:
            print(f"Background model loading failed: {e}")

    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, load_models)
    
    yield
    
    # Shutdown
    print("Shutting down...")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="P&ID/PFD Digitization Tool - Upload, annotate, and export engineering drawings",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173", "http://localhost", "http://localhost:80"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(annotations.router)
app.include_router(symbols.router)
app.include_router(export.router)
app.include_router(inference.router)

# Serve static files (rendered images, symbols)
app.mount("/static/rendered", StaticFiles(directory=str(settings.RENDERED_DIR)), name="rendered")
app.mount("/static/symbols", StaticFiles(directory=str(settings.SYMBOLS_DIR)), name="symbols")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "name": settings.APP_NAME,
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/api/health")
async def health_check():
    """API health check."""
    return {"status": "healthy"}
