"""
YOLOv8-based P&ID Symbol Detector Service

Uses the AWS pretrained P&ID model or custom YOLOv8 model for symbol detection.
Also includes EasyOCR for tag ID extraction.
"""

import asyncio
from pathlib import Path
from typing import List, Dict, Any, Tuple
import cv2
import numpy as np
from PIL import Image

# Lazy imports for heavy dependencies
_yolo_model = None
_ocr_reader = None


def get_yolo_model():
    """Lazy load YOLOv8 model."""
    global _yolo_model
    if _yolo_model is None:
        from ultralytics import YOLO
        
        # Priority: custom model > AWS model > pretrained YOLO
        models_dir = Path(__file__).parent.parent / "models"
        
        # Check for custom trained model first
        custom_model = models_dir / "yolo" / "best.pt"
        if custom_model.exists():
            print(f"Loading custom YOLO model: {custom_model}")
            _yolo_model = YOLO(str(custom_model))
        
        # Check for AWS pretrained model
        elif (models_dir / "aws_pid").exists():
            aws_model = models_dir / "aws_pid" / "model.pt"
            if aws_model.exists():
                print(f"Loading AWS P&ID model: {aws_model}")
                _yolo_model = YOLO(str(aws_model))
            else:
                print("AWS model directory exists but model.pt not found, using YOLOv8n")
                _yolo_model = YOLO("yolov8n.pt")
        
        else:
            # Fall back to pretrained YOLOv8 (will detect generic objects, not P&ID symbols)
            print("No P&ID model found, using pretrained YOLOv8n")
            _yolo_model = YOLO("yolov8n.pt")
    
    return _yolo_model


def get_ocr_reader():
    """Lazy load EasyOCR reader."""
    global _ocr_reader
    if _ocr_reader is None:
        try:
            import easyocr
            print("Loading EasyOCR reader...")
            _ocr_reader = easyocr.Reader(['en'], gpu=False)  # Use CPU for Docker compatibility
        except ImportError:
            print("EasyOCR not available")
            _ocr_reader = False  # Mark as unavailable
    return _ocr_reader if _ocr_reader else None


async def detect_symbols(
    image_path: str,
    confidence_threshold: float = 0.25,
    iou_threshold: float = 0.45
) -> List[Dict[str, Any]]:
    """
    Detect P&ID symbols in an image using YOLOv8.
    
    Args:
        image_path: Path to the image file
        confidence_threshold: Minimum confidence for detections
        iou_threshold: IoU threshold for NMS
    
    Returns:
        List of detections with bounding boxes, class, and confidence
    """
    model = get_yolo_model()
    
    # Run inference in thread pool to avoid blocking
    def run_inference():
        results = model.predict(
            source=image_path,
            conf=confidence_threshold,
            iou=iou_threshold,
            verbose=False
        )
        return results[0] if results else None
    
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, run_inference)
    
    if result is None:
        return []
    
    detections = []
    boxes = result.boxes
    
    for i in range(len(boxes)):
        box = boxes[i]
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        conf = float(box.conf[0])
        cls_id = int(box.cls[0])
        cls_name = result.names.get(cls_id, f"class_{cls_id}")
        
        detections.append({
            "bbox": {
                "x": int(x1),
                "y": int(y1),
                "width": int(x2 - x1),
                "height": int(y2 - y1)
            },
            "class_id": cls_id,
            "class_name": cls_name,
            "confidence": round(conf, 3),
            "source": "yolo"
        })
    
    return detections


async def extract_text_regions(
    image_path: str,
    min_confidence: float = 0.3
) -> List[Dict[str, Any]]:
    """
    Extract text/tag IDs from P&ID using OCR.
    
    Args:
        image_path: Path to the image file
        min_confidence: Minimum OCR confidence
    
    Returns:
        List of text detections with bounding boxes and text content
    """
    reader = get_ocr_reader()
    if reader is None:
        return []
    
    def run_ocr():
        results = reader.readtext(image_path)
        return results
    
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, run_ocr)
    
    text_regions = []
    for bbox, text, conf in results:
        if conf < min_confidence:
            continue
        
        # bbox is [[x1,y1], [x2,y1], [x2,y2], [x1,y2]]
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


def classify_tag(text: str) -> str:
    """
    Classify a text string as a tag type.
    
    Common P&ID tag patterns:
    - FIC-101 (Flow Indicator Controller)
    - PV-2001 (Pressure Valve)
    - LT-150 (Level Transmitter)
    """
    import re
    
    text = text.strip().upper()
    
    # Instrument tag pattern: 2-3 letters + number
    if re.match(r'^[A-Z]{2,4}[-_]?\d{2,5}[A-Z]?$', text):
        return "instrument_tag"
    
    # Equipment tag pattern: letters + numbers
    if re.match(r'^[A-Z]{1,2}[-_]?\d{3,5}$', text):
        return "equipment_tag"
    
    # Line number pattern
    if re.match(r'^\d{1,2}"-.*$', text) or re.match(r'^\d{1,3}mm.*$', text):
        return "line_number"
    
    return "text"


async def detect_lines(
    image_path: str,
    min_length: int = 50
) -> List[Dict[str, Any]]:
    """
    Detect process lines using Hough transform.
    
    Args:
        image_path: Path to image
        min_length: Minimum line length in pixels
    
    Returns:
        List of line segments with start/end points
    """
    def run_line_detection():
        img = cv2.imread(image_path)
        if img is None:
            return []
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        
        # Probabilistic Hough Transform
        lines = cv2.HoughLinesP(
            edges, 
            rho=1, 
            theta=np.pi/180, 
            threshold=80,
            minLineLength=min_length,
            maxLineGap=10
        )
        
        if lines is None:
            return []
        
        result = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            length = np.sqrt((x2-x1)**2 + (y2-y1)**2)
            angle = np.arctan2(y2-y1, x2-x1) * 180 / np.pi
            
            result.append({
                "start": {"x": int(x1), "y": int(y1)},
                "end": {"x": int(x2), "y": int(y2)},
                "length": int(length),
                "angle": round(angle, 1)
            })
        
        return result
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, run_line_detection)


async def full_analysis(
    image_path: str,
    detect_symbols_flag: bool = True,
    extract_text_flag: bool = True,
    detect_lines_flag: bool = False
) -> Dict[str, Any]:
    """
    Run full P&ID analysis pipeline.
    
    Returns combined results from all detection modules.
    """
    results = {}
    
    tasks = []
    if detect_symbols_flag:
        tasks.append(("symbols", detect_symbols(image_path)))
    if extract_text_flag:
        tasks.append(("text", extract_text_regions(image_path)))
    if detect_lines_flag:
        tasks.append(("lines", detect_lines(image_path)))
    
    # Run all tasks concurrently
    for name, task in tasks:
        try:
            results[name] = await task
        except Exception as e:
            results[name] = {"error": str(e)}
    
    # Add summary
    results["summary"] = {
        "total_symbols": len(results.get("symbols", [])),
        "total_text": len(results.get("text", [])),
        "total_lines": len(results.get("lines", []))
    }
    
    return results
