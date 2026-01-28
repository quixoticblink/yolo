from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


# Auth schemas
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class UserCreate(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    created_at: datetime

    class Config:
        from_attributes = True


# Document schemas
class DocumentCreate(BaseModel):
    filename: str


class DocumentResponse(BaseModel):
    id: int
    filename: str
    page_count: int
    status: str
    uploaded_at: datetime

    class Config:
        from_attributes = True


class PageResponse(BaseModel):
    id: int
    page_number: int
    image_path: str
    width: Optional[int]
    height: Optional[int]

    class Config:
        from_attributes = True


# Symbol schemas
class SymbolCreate(BaseModel):
    name: str
    category: str
    description: Optional[str] = None


class SymbolResponse(BaseModel):
    id: int
    name: str
    category: str
    image_path: Optional[str]
    description: Optional[str]

    class Config:
        from_attributes = True


# Annotation schemas
class AnnotationCreate(BaseModel):
    page_id: int
    symbol_id: Optional[int] = None
    x: float
    y: float
    width: float
    height: float
    tag_id: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = {}
    confidence: Optional[float] = None
    source: str = "manual"


class AnnotationUpdate(BaseModel):
    symbol_id: Optional[int] = None
    x: Optional[float] = None
    y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    tag_id: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None


class AnnotationResponse(BaseModel):
    id: int
    page_id: int
    symbol_id: Optional[int]
    x: float
    y: float
    width: float
    height: float
    tag_id: Optional[str]
    attributes: Dict[str, Any]
    confidence: Optional[float]
    source: str
    created_at: datetime

    class Config:
        from_attributes = True


# Connection schemas
class ConnectionCreate(BaseModel):
    page_id: int
    from_annotation_id: int
    to_annotation_id: int
    line_type: str = "process"
    waypoints: List[Dict[str, float]] = []


class ConnectionResponse(BaseModel):
    id: int
    page_id: int
    from_annotation_id: int
    to_annotation_id: int
    line_type: str
    waypoints: List[Dict[str, float]]
    created_at: datetime

    class Config:
        from_attributes = True


# AI Inference schemas
class InferenceRequest(BaseModel):
    page_id: int
    model: str = "yolo"  # yolo, aws


class DetectionResult(BaseModel):
    x: float
    y: float
    width: float
    height: float
    class_name: str
    confidence: float


class InferenceResponse(BaseModel):
    page_id: int
    model: str
    detections: List[DetectionResult]
