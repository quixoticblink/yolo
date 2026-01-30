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


# Global model manager
_model_manager = None

# Global OCR reader (lazy loaded)
_ocr_reader = None

class ModelManager:
    def __init__(self):
        self.active_model_name = "aws_frcnn"
        self.loaded_models = {}
        self.available_models = [
            {"id": "aws_frcnn", "name": "AWS P&ID Model (Faster R-CNN)", "type": "aws", "path": "default"}
        ]
        # Discover custom models
        self.discover_custom_models()

    def discover_custom_models(self):
        custom_dir = MODELS_DIR / "custom"
        if custom_dir.exists():
            for model_path in custom_dir.glob("*.pt"):
                model_id = model_path.stem
                self.available_models.append({
                    "id": model_id,
                    "name": f"Custom: {model_path.name}",
                    "type": "yolo",
                    "path": str(model_path)
                })

    def get_active_model(self):
        return self.get_model(self.active_model_name)

    def get_model(self, model_id):
        # Find model config
        config = next((m for m in self.available_models if m["id"] == model_id), None)
        if not config:
            raise ValueError(f"Model {model_id} not found")

        # Check if loaded
        if model_id in self.loaded_models and self.loaded_models[model_id] is not None:
             return self.loaded_models[model_id]

        # Load model
        print(f"Loading model: {model_id} ({config['type']})")
        if config["type"] == "aws":
            model = load_aws_model()
        elif config["type"] == "yolo":
            model = load_yolo_model(config["path"])
        else:
            raise ValueError(f"Unknown model type: {config['type']}")
        
        self.loaded_models[model_id] = model
        return model

    def set_active_model(self, model_id):
        # Validate existence
        if not any(m["id"] == model_id for m in self.available_models):
            raise ValueError(f"Model {model_id} not found")
        
        self.active_model_name = model_id
        # Trigger load
        self.get_model(model_id)
        return {"active_model": model_id}

    def list_models(self):
        return [
            {**m, "active": m["id"] == self.active_model_name}
            for m in self.available_models
        ]

def get_model_manager():
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager

# Backwards compatibility wrapper for startup preloading
def get_aws_models():
    manager = get_model_manager()
    # Ensure AWS model is loaded if it's the active one (default)
    if manager.active_model_name == "aws_frcnn":
        return manager.get_active_model()
    return manager.get_model("aws_frcnn")

def load_aws_model():
    """Load AWS Faster R-CNN + Siamese models."""
    rcnn_path = MODELS_DIR / "frcnn_checkpoint_50000.pth"
    siamese_path = MODELS_DIR / "last-v9.ckpt"
    references_dir = MODELS_DIR / "references"
    
    if not rcnn_path.exists():
        print(f"AWS RCNN model not found at {rcnn_path}")
        return None
    
    try:
        from torchvision.models.detection import fasterrcnn_resnet50_fpn
        
        # Load RCNN model
        checkpoint = torch.load(rcnn_path, map_location=DEVICE, weights_only=False)
        rcnn_model = fasterrcnn_resnet50_fpn(pretrained=False, num_classes=2)
        
        if "model_state_dict" in checkpoint:
            rcnn_model.load_state_dict(checkpoint["model_state_dict"])
        elif "state_dict" in checkpoint:
            rcnn_model.load_state_dict(checkpoint["state_dict"])
        else:
            rcnn_model.load_state_dict(checkpoint)
        
        rcnn_model.eval().to(DEVICE)
        
        # Load Siamese model
        siamese_model = None
        reference_embeddings = {}
        class_id_mapping = {}
        
        if siamese_path.exists():
            try:
                from siamese_lightning import SiameseLightningModule
                siamese_model = SiameseLightningModule.load_from_checkpoint(
                    siamese_path, map_location=DEVICE
                )
                siamese_model.eval().to(DEVICE)
                
                if references_dir.exists():
                    from inference import get_reference_embeddings
                    reference_embeddings, class_id_mapping = get_reference_embeddings(
                        references_dir, siamese_model
                    )
            except Exception as e:
                print(f"Siamese model loading failed: {e}")
        
        return {
            "type": "aws",
            "rcnn": rcnn_model,
            "siamese": siamese_model,
            "reference_embeddings": reference_embeddings,
            "class_id_mapping": class_id_mapping,
        }
    except Exception as e:
        print(f"AWS model loading failed: {e}")
        return None

def load_yolo_model(path):
    """Load custom YOLOv8 model."""
    try:
        from ultralytics import YOLO
        model = YOLO(path)
        return {
            "type": "yolo",
            "model": model
        }
    except Exception as e:
        print(f"YOLO model loading failed: {e}")
        return None

async def detect_symbols(
    image_path: str,
    confidence_threshold: float = 0.25  # Lowered from 0.5 for better recall on P&IDs
) -> List[Dict[str, Any]]:
    """
    Detect P&ID symbols using ACTIVE model.
    """
    manager = get_model_manager()
    
    def run_inference():
        # Load model inside thread
        model_data = manager.get_active_model()
        
        if model_data is None:
            return []
            
        img = Image.open(image_path).convert("RGB")
        
        # Dispatch based on model type
        if model_data["type"] == "aws":
            return run_aws_inference(model_data, img, confidence_threshold)
        elif model_data["type"] == "yolo":
            return run_yolo_inference(model_data, img, confidence_threshold)
        else:
            print(f"Unknown model type: {model_data.get('type')}")
            return []

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, run_inference)

def run_aws_inference(model_data, img, confidence_threshold):
    # (Original inference logic extracted here)
    rcnn_model = model_data["rcnn"]
    siamese_model = model_data["siamese"]
    reference_embeddings = model_data.get("reference_embeddings", {})
    class_id_mapping = model_data.get("class_id_mapping", {})
    
    img_array = np.array(img).astype(np.float32) / 255.0
    img_tensor = torch.tensor(img_array).permute(2, 0, 1).to(DEVICE)
    
    with torch.no_grad():
        outputs = rcnn_model([img_tensor])[0]
    
    detections = []
    boxes = outputs["boxes"].cpu().numpy()
    scores = outputs["scores"].cpu().numpy()
    
    # Apply NMS to reduce duplicate overlapping boxes
    from torchvision.ops import nms
    keep_indices = nms(
        torch.tensor(boxes), 
        torch.tensor(scores), 
        iou_threshold=0.4  # Merge boxes with >40% overlap
    ).numpy()
    boxes = boxes[keep_indices]
    scores = scores[keep_indices]
    
    for i, (box, score) in enumerate(zip(boxes, scores)):
        if score < confidence_threshold:
            continue
        
        x1, y1, x2, y2 = box.astype(int)
        
        class_name = "symbol"
        class_id = 0
        embedding_distance = 0.0
        
        if siamese_model is not None and reference_embeddings:
            try:
                from inference import get_single_symbol_embedding, get_n_closest_embeddings_from_symbol
                symbol_embedding = get_single_symbol_embedding(img_array, box, 224, siamese_model)
                closest_n = get_n_closest_embeddings_from_symbol(reference_embeddings, symbol_embedding, 1)
                
                if closest_n:
                    class_name = closest_n[0][0].replace(".png", "")
                    embedding_distance = float(closest_n[0][1])
                    class_id = class_id_mapping.get(closest_n[0][0], 0)
            except Exception as e:
                print(f"Siamese classification failed for detection {i}: {e}")
                # Detection is still valid, just use default class
        
        detections.append({
            "bbox": {"x": int(x1), "y": int(y1), "width": int(x2-x1), "height": int(y2-y1)},
            "class_id": class_id,
            "class_name": class_name,
            "confidence": float(score),
            "embedding_distance": embedding_distance,
            "source": "aws_frcnn"
        })
    return detections

def run_yolo_inference(model_data, img, confidence_threshold):
    model = model_data["model"]
    results = model(img, conf=confidence_threshold)
    
    detections = []
    for r in results:
        for box in r.boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            conf = float(box.conf[0])
            cls = int(box.cls[0])
            name = model.names[cls]
            
            detections.append({
                "bbox": {"x": int(x1), "y": int(y1), "width": int(x2-x1), "height": int(y2-y1)},
                "class_id": cls,
                "class_name": name,
                "confidence": conf,
                "source": "custom_yolo"
            })
    return detections

async def extract_tag_from_symbol(image_path: str, bbox: dict) -> str:
    """
    Extract tag ID from a specific symbol's bounding box region.
    
    Crops the bbox area, applies enhancement, runs OCR, and returns best tag match.
    """
    import re
    import cv2
    
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr
        _ocr_reader = easyocr.Reader(['en'], gpu=torch.cuda.is_available())
    
    # Load image
    img = cv2.imread(image_path)
    if img is None:
        return None
    
    h, w = img.shape[:2]
    
    # Get bbox with moderate padding (enough to capture nearby labels but not too large)
    pad_x = min(100, max(50, bbox["width"]))
    pad_y = min(80, max(40, bbox["height"]))
    
    x1 = max(0, int(bbox["x"] - pad_x))
    y1 = max(0, int(bbox["y"] - pad_y))
    x2 = min(w, int(bbox["x"] + bbox["width"] + pad_x))
    y2 = min(h, int(bbox["y"] + bbox["height"] + pad_y))
    
    crop = img[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    
    # Upscale 2x for faster processing (was 3x)
    scale_factor = 2.0
    crop_scaled = cv2.resize(crop, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)
    
    # Convert to grayscale and apply CLAHE
    gray = cv2.cvtColor(crop_scaled, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    
    # Run OCR
    results = _ocr_reader.readtext(enhanced)
    
    # Find best tag-like text
    # Tag patterns: 4010, #95, FIC-101, etc.
    tag_pattern = re.compile(r'^[#]?\d{2,5}$|^[A-Z]{1,4}[-_]?\d+[A-Z]?$', re.IGNORECASE)
    
    best_tag = None
    best_confidence = 0
    
    for ocr_bbox, text, conf in results:
        text = text.strip()
        if len(text) < 2 or len(text) > 15:
            continue
        
        # Check if it matches tag pattern
        if tag_pattern.match(text):
            if conf > best_confidence:
                best_tag = text
                best_confidence = conf
    
    if best_tag:
        print(f"Per-symbol OCR found tag: {best_tag} (conf: {best_confidence:.2f})")
    
    return best_tag

async def extract_text_regions(
    image_path: str,
    min_confidence: float = 0.3,
    focus_regions: List[Dict[str, Any]] = None  # List of bboxes to specifically check
) -> List[Dict[str, Any]]:
    # (Same as before)
    try:
        import easyocr
        import cv2
        _ocr_reader = easyocr.Reader(['en'], gpu=False)
        
        # Pass 1: Original Image
        results = _ocr_reader.readtext(image_path)
        
        # Pass 2: Rotated 90 degrees Clockwise (to read bottom-to-top vertical text)
        img = cv2.imread(str(image_path))
        if img is None:
            return []

        # Apply mild sharpening to improve OCR on blurry/scanned images
        kernel = np.array([[0, -0.5, 0],
                           [-0.5, 3, -0.5],
                           [0, -0.5, 0]])
        img = cv2.filter2D(img, -1, kernel)

        img_90 = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
        results_90 = _ocr_reader.readtext(img_90)
        
        # Transform coordinates back to original frame
        h, w = img.shape[:2]
        for bbox, text, conf in results_90:
            new_bbox = [[int(pt[1]), int(h - pt[0])] for pt in bbox]
            results.append((new_bbox, text, conf))

        # Pass 3: Focus Regions (Local OCR)
        # Often tags inside symbols are missed by full-page scan. 
        # We crop around each symbol and run OCR specifically there.
        if focus_regions:
            print(f"Running Local OCR on {len(focus_regions)} focus regions...")
            for region in focus_regions:
                # Crop with padding
                cx = region["x"] + region["width"] / 2
                cy = region["y"] + region["height"] / 2
                pad_x = max(100, region["width"]) # Ensure enough context
                pad_y = max(100, region["height"]) 
                
                x1 = max(0, int(cx - pad_x))
                y1 = max(0, int(cy - pad_y))
                x2 = min(w, int(cx + pad_x))
                y2 = min(h, int(cy + pad_y))
                
                crop = img[y1:y2, x1:x2]
                if crop.size == 0: continue
                
                # Enhance crop for better OCR:
                # 1. Upscale 2x for small text
                crop_scaled = cv2.resize(crop, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
                
                # 2. Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
                gray = cv2.cvtColor(crop_scaled, cv2.COLOR_BGR2GRAY)
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
                enhanced = clahe.apply(gray)
                
                # Run OCR on enhanced grayscale crop
                crop_results = _ocr_reader.readtext(enhanced)
                
                # Transform back to global coordinates (account for 2x scale)
                for bbox, text, conf in crop_results:
                    new_bbox = [[int(pt[0]/2 + x1), int(pt[1]/2 + y1)] for pt in bbox]
                    results.append((new_bbox, text, conf))

        text_regions = []
        seen_texts = set() # Simple de-duplication
        
        for bbox, text, conf in results:
            if conf < min_confidence:
                continue
            
            # Simple de-dupe by text content and approx location logic could go here, 
            # but for now we rely on the tag matcher to pick the best one.
            # We just ensure we don't output exact duplicate objects if easyocr returns them.
            
            points = np.array(bbox)
            x1, y1 = points.min(axis=0)
            x2, y2 = points.max(axis=0)
            
            region_obj = {
                "bbox": {"x": int(x1), "y": int(y1), "width": int(x2-x1), "height": int(y2-y1)},
                "text": text,
                "confidence": round(float(conf), 3),
                "type": classify_tag(text)
            }
            text_regions.append(region_obj)
            
        return text_regions
    except Exception as e:
        print(f"OCR failed: {e}")
        return []

def classify_tag(text: str) -> str:
    # (Same as before)
    import re
    text = text.strip().upper()
    if re.match(r'^[A-Z]{2,4}[-_]?\d{2,5}[A-Z]?$', text): return "instrument_tag"
    if re.match(r'^[A-Z]{1,2}[-_]?\d{3,5}$', text): return "equipment_tag"
    if re.match(r'^\d{1,2}"-.*$', text) or re.match(r'^\d{1,3}mm.*$', text): return "line_number"
    return "text"

async def full_analysis(
    image_path: str,
    detect_symbols_flag: bool = True,
    extract_text_flag: bool = False,
    detect_lines_flag: bool = False
) -> Dict[str, Any]:
    # (Same as before)
    results = {}
    if detect_symbols_flag:
        try: results["symbols"] = await detect_symbols(image_path)
        except Exception as e: results["symbols"] = {"error": str(e)}
    if extract_text_flag:
        try: 
            # Use detected symbols (if any) as focus regions for Local OCR
            focus_regions = [s["bbox"] for s in results.get("symbols", [])] if detect_symbols_flag else None
            results["text"] = await extract_text_regions(image_path, focus_regions=focus_regions)
        except Exception as e: results["text"] = {"error": str(e)}
    results["summary"] = {
        "total_symbols": len(results.get("symbols", [])) if isinstance(results.get("symbols"), list) else 0,
        "total_text": len(results.get("text", [])) if isinstance(results.get("text"), list) else 0,
    }
    return results
