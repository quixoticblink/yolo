"""
AI Inference API endpoints for P&ID analysis.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from ..database import get_db
from ..models import Document, Page, Annotation, User
from ..auth import get_current_user
from ..config import settings

router = APIRouter(prefix="/api/inference", tags=["Inference"])


@router.post("/{document_id}/detect")
async def detect_symbols_in_document(
    document_id: int,
    page_number: int = 1,
    confidence: float = 0.25,
    extract_text: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Run AI detection on a document page.
    
    Returns detected symbols and text (tag IDs) without saving to database.
    Use this to preview detections before accepting them.
    """
    from services.yolo_detector import full_analysis
    
    # Get page image path
    result = await db.execute(
        select(Page)
        .where(Page.document_id == document_id, Page.page_number == page_number)
    )
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    # Run detection
    try:
        analysis = await full_analysis(
            page.image_path,
            detect_symbols_flag=True,
            extract_text_flag=extract_text,
            detect_lines_flag=False
        )
        return {
            "document_id": document_id,
            "page_number": page_number,
            "page_width": page.width,
            "page_height": page.height,
            **analysis
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")


@router.post("/{document_id}/auto-annotate")
async def auto_annotate_document(
    document_id: int,
    page_number: int = 1,
    confidence: float = 0.5,
    use_ocr: bool = True,  # Enabled by default to extract tag IDs
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Run AI detection and automatically create annotations.
    
    - Detects symbols using AWS Faster R-CNN
    - Matches symbols to library using Siamese network
    - Extracts text (tag IDs) using OCR and associates with nearby symbols
    """
    from services.yolo_detector import detect_symbols, extract_text_regions
    from ..models import Symbol
    
    # Get page
    result = await db.execute(
        select(Page)
        .where(Page.document_id == document_id, Page.page_number == page_number)
    )
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    # Get all symbols from DB for matching
    symbols_result = await db.execute(select(Symbol))
    db_symbols = {s.name.lower(): s.id for s in symbols_result.scalars().all()}
    
    # Run symbol detection
    try:
        detected_symbols = await detect_symbols(page.image_path, confidence)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Symbol detection failed: {str(e)}")
    
    # Run OCR for text/tag extraction
    text_regions = []
    if use_ocr:
        try:
            text_regions = await extract_text_regions(page.image_path)
            print(f"OCR extracted {len(text_regions)} text regions")
        except Exception as e:
            print(f"OCR failed (continuing without): {e}")
    
    # Create annotations for each detected symbol
    created_annotations = []
    for detection in detected_symbols:
        bbox = detection["bbox"]
        class_name = detection.get("class_name", "symbol")
        
        # Find matching symbol_id from database
        symbol_id = None
        # Try exact match first
        if class_name.lower() in db_symbols:
            symbol_id = db_symbols[class_name.lower()]
        else:
            # Try partial match
            for sym_name, sym_id in db_symbols.items():
                if class_name.lower() in sym_name or sym_name in class_name.lower():
                    symbol_id = sym_id
                    break
        
        # Find nearby text (potential tag ID)
        tag_id = find_nearby_tag(bbox, text_regions) if text_regions else None
        
        annotation = Annotation(
            page_id=page.id,
            symbol_id=symbol_id,
            x=bbox["x"],
            y=bbox["y"],
            width=bbox["width"],
            height=bbox["height"],
            tag_id=tag_id,
            confidence=detection["confidence"],
            source="aws",
            created_by=current_user.id,
            attributes={
                "class_name": class_name,
                "embedding_distance": detection.get("embedding_distance", 0)
            }
        )
        db.add(annotation)
        created_annotations.append({
            "class_name": class_name,
            "symbol_id": symbol_id,
            "confidence": detection["confidence"],
            "tag_id": tag_id,
            "bbox": bbox
        })
    
    await db.commit()
    
    return {
        "document_id": document_id,
        "page_number": page_number,
        "annotations_created": len(created_annotations),
        "annotations": created_annotations,
        "text_detected": len(text_regions),
        "ocr_used": use_ocr
    }


def find_nearby_tag(bbox: dict, text_regions: list, max_distance: int = 100) -> Optional[str]:
    """
    Find a tag ID text region near a symbol bounding box.
    
    Looks for instrument/equipment tags within max_distance pixels
    of the symbol, preferring tags above or to the right of the symbol.
    """
    symbol_center_x = bbox["x"] + bbox["width"] / 2
    symbol_center_y = bbox["y"] + bbox["height"] / 2
    
    best_tag = None
    best_distance = float("inf")
    
    for text in text_regions:
        # Only consider instrument/equipment tags
        if text["type"] not in ["instrument_tag", "equipment_tag"]:
            continue
        
        text_bbox = text["bbox"]
        text_center_x = text_bbox["x"] + text_bbox["width"] / 2
        text_center_y = text_bbox["y"] + text_bbox["height"] / 2
        
        # Calculate distance
        distance = ((symbol_center_x - text_center_x) ** 2 + 
                   (symbol_center_y - text_center_y) ** 2) ** 0.5
        
        if distance < max_distance and distance < best_distance:
            best_distance = distance
            best_tag = text["text"]
    
    return best_tag


@router.get("/status")
async def get_inference_status():
    """
    Check if AI models are loaded and ready.
    """
    from pathlib import Path
    
    models_dir = Path(__file__).parent.parent.parent / "models"
    
    status = {
        "models_dir": str(models_dir),
        "yolo_ready": False,
        "ocr_ready": False,
        "available_models": []
    }
    
    # Check for YOLO models
    if (models_dir / "yolo" / "best.pt").exists():
        status["available_models"].append("custom_yolo")
    if (models_dir / "aws_pid").exists():
        status["available_models"].append("aws_pid")
    
    # Try loading models
    try:
        from services.yolo_detector import get_yolo_model, get_ocr_reader
        
        model = get_yolo_model()
        status["yolo_ready"] = model is not None
        status["yolo_classes"] = len(model.names) if model else 0
        
        ocr = get_ocr_reader()
        status["ocr_ready"] = ocr is not None
        
    except Exception as e:
        status["error"] = str(e)
    
    return status
