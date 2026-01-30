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
    
    # Import per-symbol OCR function
    from services.yolo_detector import extract_tag_from_symbol
    
    print(f"Detected {len(detected_symbols)} symbols, running per-symbol OCR...")
    
    # Create annotations for each detected symbol
    created_annotations = []
    for detection in detected_symbols:
        bbox = detection["bbox"]
        class_name = detection.get("class_name", "symbol")
        
        # Find matching symbol_id from database
        symbol_id = None
        
        # Normalize class name for matching (AWS uses underscores, DB uses spaces)
        search_name = class_name.lower().replace("_", " ").replace(".png", "")
        
        # Try exact match with normalized name
        if search_name in db_symbols:
            symbol_id = db_symbols[search_name]
        else:
            # Try matching by base name (e.g. "Gate Valve 001" -> "Gate Valve")
            # This helps if we have generic symbols in DB but specific ones from AWS
            base_name = search_name
            if any(char.isdigit() for char in base_name):
                base_name = "".join([i for i in base_name if not i.isdigit()]).strip()
                if base_name in db_symbols:
                    symbol_id = db_symbols[base_name]
            
            # Fallback to partial match
            if not symbol_id:
                for sym_name, sym_id in db_symbols.items():
                    if search_name in sym_name or sym_name in search_name:
                        symbol_id = sym_id
                        break
        
        # Run per-symbol OCR to extract tag ID from this specific bbox
        tag_id = None
        if use_ocr:
            try:
                tag_id = await extract_tag_from_symbol(page.image_path, bbox)
            except Exception as e:
                print(f"Per-symbol OCR failed for bbox {bbox}: {e}")
        
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
        "ocr_used": use_ocr
    }


def find_nearby_tag(bbox: dict, text_regions: list, max_distance: int = 350) -> Optional[str]:
    """
    Find a tag ID text region near or inside a symbol bounding box.
    
    Search priority:
    1. Text overlapping with the symbol bbox
    2. Text directly above the symbol
    3. Text to the right of the symbol
    4. Any nearby text within max_distance
    """
    import re
    
    symbol_x1, symbol_y1 = bbox["x"], bbox["y"]
    symbol_x2 = symbol_x1 + bbox["width"]
    symbol_y2 = symbol_y1 + bbox["height"]
    symbol_center_x = (symbol_x1 + symbol_x2) / 2
    symbol_center_y = (symbol_y1 + symbol_y2) / 2
    
    candidates = []
    
    for text in text_regions:
        text_bbox = text["bbox"]
        text_x1, text_y1 = text_bbox["x"], text_bbox["y"]
        text_x2 = text_x1 + text_bbox["width"]
        text_y2 = text_y1 + text_bbox["height"]
        text_center_x = (text_x1 + text_x2) / 2
        text_center_y = (text_y1 + text_y2) / 2
        
        # Skip very short or very long text (unlikely to be a tag)
        text_content = text["text"].strip()
        if len(text_content) < 2 or len(text_content) > 20:
            continue
        
        # Skip very generic text (but allow numbers like 4103)
        if text_content.lower() in ["the", "and", "or", "a", "an"]:
            continue
        
        # Calculate distance
        distance = ((symbol_center_x - text_center_x) ** 2 + 
                   (symbol_center_y - text_center_y) ** 2) ** 0.5
        
        if distance > max_distance:
            continue
        
        # Check if text overlaps with symbol
        overlap_x = max(0, min(symbol_x2, text_x2) - max(symbol_x1, text_x1))
        overlap_y = max(0, min(symbol_y2, text_y2) - max(symbol_y1, text_y1))
        overlaps = overlap_x > 0 and overlap_y > 0
        
        # Check if text is fully inside the symbol bounding box
        is_inside = (text_x1 >= symbol_x1 and text_x2 <= symbol_x2 and 
                     text_y1 >= symbol_y1 and text_y2 <= symbol_y2)
        
        # Position scoring (prefer text above or to the right)
        is_above = text_y2 < symbol_y1 + bbox["height"] * 0.3
        is_right = text_x1 > symbol_x2 - bbox["width"] * 0.3
        is_tag_pattern = bool(re.match(r'^[#]?\d{2,}$|^[A-Z]{1,4}[-_]?\d+[A-Z]?$', text_content.upper()))  # Match #95, 4105, FIC-101
        
        # Priority score (lower is better)
        priority = 1000
        if is_inside:  # Highest priority: text is inside the symbol box
            priority = 0
        elif overlaps:
            priority = 5
        elif is_above and is_tag_pattern:
            priority = 10
        elif is_right and is_tag_pattern:
            priority = 20
        elif is_tag_pattern:
            priority = 50
        elif is_above:
            priority = 100
        elif is_right:
            priority = 150
        
        candidates.append({
            "text": text_content,
            "distance": distance,
            "priority": priority,
            "type": text["type"]
        })
    
    if not candidates:
        return None
    
    # Sort by priority first, then by distance
    candidates.sort(key=lambda x: (x["priority"], x["distance"]))
    return candidates[0]["text"]


@router.get("/status")
async def get_inference_status():
    """
    Check if AI models are loaded and ready.
    """
    from services.yolo_detector import get_model_manager
    
    manager = get_model_manager()
    active_model = manager.get_active_model()
    
    status = {
        "active_model": manager.active_model_name,
        "available_models": [m["id"] for m in manager.available_models],
        "model_loaded": active_model is not None,
        "ocr_ready": False
    }
    
    # Check OCR
    try:
        import easyocr
        # Just check if we can instantiate or if library is present
        status["ocr_ready"] = True
    except ImportError:
        status["ocr_ready"] = False
    except Exception as e:
        status["ocr_error"] = str(e)
    
    return status
