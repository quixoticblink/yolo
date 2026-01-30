from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import List, Dict, Any
from services.yolo_detector import get_model_manager

router = APIRouter(prefix="/api/models", tags=["AI Models"])

@router.get("/", response_model=List[Dict[str, Any]])
def list_models():
    """
    List all available AI models.
    Returns list of models including their active status.
    """
    manager = get_model_manager()
    return manager.list_models()

@router.post("/{model_id}/activate")
def activate_model(model_id: str):
    """
    Switch the active AI model for detection.
    The selected model will be used for all subsequent 'auto-detect' calls.
    P&ID inference is stateful per server instance.
    """
    manager = get_model_manager()
    try:
        result = manager.set_active_model(model_id)
        return {
            "message": f"Model switched to {model_id}",
            "active_model": result["active_model"]
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to activate model: {str(e)}")

@router.get("/status")
def get_model_status():
    """Get currently active model info."""
    manager = get_model_manager()
    # Find active model info
    active_id = manager.active_model_name
    models = manager.list_models()
    active_info = next((m for m in models if m["id"] == active_id), None)
    
    return {
        "active_model_id": active_id,
        "active_model_info": active_info
    }
