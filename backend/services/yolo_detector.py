"""
AWS Faster R-CNN P&ID Symbol Detector Service

Uses the AWS pretrained Faster R-CNN + Siamese network for P&ID symbol detection.
Falls back to basic detection if reference embeddings not available.
"""

import asyncio
import sys
from pathlib import Path
from typing import List, Dict, Any
import numpy as np
from PIL import Image
import torch

# Add models/code to path for importing AWS model code
MODELS_DIR = Path(__file__).parent.parent / "models"
CODE_DIR = MODELS_DIR / "code"
if CODE_DIR.exists():
    sys.path.insert(0, str(MODELS_DIR))
    sys.path.insert(0, str(CODE_DIR))

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Lazy loaded models
_aws_models = None


def get_aws_models():
    """Lazy load AWS Faster R-CNN + Siamese models."""
    global _aws_models
    if _aws_models is not None:
        return _aws_models
    
    rcnn_path = MODELS_DIR / "frcnn_checkpoint_50000.pth"
    siamese_path = MODELS_DIR / "last-v9.ckpt"
    references_dir = MODELS_DIR / "references"
    
    if not rcnn_path.exists():
        print(f"AWS RCNN model not found at {rcnn_path}")
        return None
    
    try:
        from torchvision.models.detection import fasterrcnn_resnet50_fpn
        
        print(f"Loading AWS Faster R-CNN model from {rcnn_path}")
        
        # Load RCNN model
        checkpoint = torch.load(rcnn_path, map_location=DEVICE, weights_only=False)
        rcnn_model = fasterrcnn_resnet50_fpn(pretrained=False, num_classes=2)
        
        # Load weights
        if "model_state_dict" in checkpoint:
            rcnn_model.load_state_dict(checkpoint["model_state_dict"])
        elif "state_dict" in checkpoint:
            rcnn_model.load_state_dict(checkpoint["state_dict"])
        else:
            print(f"Unknown checkpoint format: {checkpoint.keys()}")
            # Try loading directly
            rcnn_model.load_state_dict(checkpoint)
        
        rcnn_model.eval().to(DEVICE)
        print("Faster R-CNN model loaded successfully")
        
        # Try to load Siamese model if available
        siamese_model = None
        reference_embeddings = {}
        class_id_mapping = {}
        
        if siamese_path.exists():
            try:
                from siamese_lightning import SiameseLightningModule
                print(f"Loading Siamese model from {siamese_path}")
                siamese_model = SiameseLightningModule.load_from_checkpoint(
                    siamese_path, map_location=DEVICE
                )
                siamese_model.eval().to(DEVICE)
                print("Siamese model loaded successfully")
                
                # Load reference embeddings
                if references_dir.exists():
                    from inference import get_reference_embeddings
                    reference_embeddings, class_id_mapping = get_reference_embeddings(
                        references_dir, siamese_model
                    )
                    print(f"Loaded {len(reference_embeddings)} reference embeddings")
            except Exception as e:
                print(f"Siamese model loading failed (will use basic detection): {e}")
        
        _aws_models = {
            "rcnn": rcnn_model,
            "siamese": siamese_model,
            "reference_embeddings": reference_embeddings,
            "class_id_mapping": class_id_mapping,
        }
        return _aws_models
        
    except Exception as e:
        print(f"AWS model loading failed: {e}")
        import traceback
        traceback.print_exc()
        return None


async def detect_symbols(
    image_path: str,
    confidence_threshold: float = 0.5
) -> List[Dict[str, Any]]:
    """
    Detect P&ID symbols using AWS Faster R-CNN model.
    
    Args:
        image_path: Path to the image file
        confidence_threshold: Minimum confidence for detections
    
    Returns:
        List of detections with bounding boxes and class info
    """
    def run_inference():
        # Load models inside the thread to avoid blocking event loop
        models = get_aws_models()
        if models is None:
            print("AWS models not available, returning empty detections")
            return []

        # Load and preprocess image
        img = Image.open(image_path).convert("RGB")
        img_array = np.array(img).astype(np.float32) / 255.0
        
        rcnn_model = models["rcnn"]
        siamese_model = models["siamese"]
        reference_embeddings = models["reference_embeddings"]
        class_id_mapping = models["class_id_mapping"]
        
        # Convert to tensor
        img_tensor = torch.tensor(img_array).permute(2, 0, 1).to(DEVICE)
        
        # Run RCNN inference
        with torch.no_grad():
            outputs = rcnn_model([img_tensor])[0]
        
        detections = []
        boxes = outputs["boxes"].cpu().numpy()
        scores = outputs["scores"].cpu().numpy()
        
        for i, (box, score) in enumerate(zip(boxes, scores)):
            if score < confidence_threshold:
                continue
            
            x1, y1, x2, y2 = box
            
            # Default class info
            class_name = "symbol"
            class_id = 0
            embedding_distance = 0.0
            
            # If siamese model available, match to reference symbols
            if siamese_model is not None and reference_embeddings:
                try:
                    # Get symbol embedding
                    from inference import get_single_symbol_embedding, get_n_closest_embeddings_from_symbol
                    
                    symbol_embedding = get_single_symbol_embedding(
                        img_array, box, 224, siamese_model
                    )
                    closest_n = get_n_closest_embeddings_from_symbol(
                        reference_embeddings, symbol_embedding, 1
                    )
                    
                    if closest_n:
                        class_name = closest_n[0][0].replace(".png", "")
                        embedding_distance = float(closest_n[0][1])
                        class_id = class_id_mapping.get(closest_n[0][0], 0)
                except Exception as e:
                    print(f"Symbol matching failed: {e}")
            
            detections.append({
                "bbox": {
                    "x": int(x1),
                    "y": int(y1),
                    "width": int(x2 - x1),
                    "height": int(y2 - y1)
                },
                "class_id": class_id,
                "class_name": class_name,
                "confidence": float(score),
                "embedding_distance": embedding_distance,
                "source": "aws_frcnn"
            })
        
        return detections
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, run_inference)


async def extract_text_regions(
    image_path: str,
    min_confidence: float = 0.3
) -> List[Dict[str, Any]]:
    """
    Extract text/tag IDs from P&ID using OCR (optional, slow on first run).
    """
    try:
        import easyocr
        
        _ocr_reader = easyocr.Reader(['en'], gpu=False)
        
        results = _ocr_reader.readtext(image_path)
        
        text_regions = []
        for bbox, text, conf in results:
            if conf < min_confidence:
                continue
            
            points = np.array(bbox)
            x1, y1 = points.min(axis=0)
            x2, y2 = points.max(axis=0)
            
            text_regions.append({
                "bbox": {
                    "x": int(x1),
                    "y": int(y1),
                    "width": int(x2 - x1),
                    "height": int(y2 - y1)
                },
                "text": text,
                "confidence": round(float(conf), 3),
                "type": classify_tag(text)
            })
        
        return text_regions
    except Exception as e:
        print(f"OCR failed: {e}")
        return []


def classify_tag(text: str) -> str:
    """Classify text as tag type."""
    import re
    text = text.strip().upper()
    
    if re.match(r'^[A-Z]{2,4}[-_]?\d{2,5}[A-Z]?$', text):
        return "instrument_tag"
    if re.match(r'^[A-Z]{1,2}[-_]?\d{3,5}$', text):
        return "equipment_tag"
    if re.match(r'^\d{1,2}"-.*$', text) or re.match(r'^\d{1,3}mm.*$', text):
        return "line_number"
    
    return "text"


async def full_analysis(
    image_path: str,
    detect_symbols_flag: bool = True,
    extract_text_flag: bool = False,
    detect_lines_flag: bool = False
) -> Dict[str, Any]:
    """Run full P&ID analysis pipeline."""
    results = {}
    
    if detect_symbols_flag:
        try:
            results["symbols"] = await detect_symbols(image_path)
        except Exception as e:
            results["symbols"] = {"error": str(e)}
    
    if extract_text_flag:
        try:
            results["text"] = await extract_text_regions(image_path)
        except Exception as e:
            results["text"] = {"error": str(e)}
    
    results["summary"] = {
        "total_symbols": len(results.get("symbols", [])) if isinstance(results.get("symbols"), list) else 0,
        "total_text": len(results.get("text", [])) if isinstance(results.get("text"), list) else 0,
    }
    
    return results
