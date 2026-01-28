from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


class User(Base):
    """User model for authentication."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    documents = relationship("Document", back_populates="uploaded_by_user")
    annotations = relationship("Annotation", back_populates="created_by_user")


class Document(Base):
    """Uploaded P&ID/PFD document."""
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    original_path = Column(String(500), nullable=False)
    page_count = Column(Integer, default=1)
    status = Column(String(50), default="uploaded")  # uploaded, processing, ready, error
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    
    uploaded_by_user = relationship("User", back_populates="documents")
    pages = relationship("Page", back_populates="document", cascade="all, delete-orphan")


class Page(Base):
    """Individual page of a document."""
    __tablename__ = "pages"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    page_number = Column(Integer, nullable=False)
    image_path = Column(String(500), nullable=False)
    width = Column(Integer)
    height = Column(Integer)
    
    document = relationship("Document", back_populates="pages")
    annotations = relationship("Annotation", back_populates="page", cascade="all, delete-orphan")
    connections = relationship("Connection", back_populates="page", cascade="all, delete-orphan")


class Symbol(Base):
    """Symbol from the legend library."""
    __tablename__ = "symbols"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    category = Column(String(100), nullable=False)  # Equipment, Valves, Piping, etc.
    image_path = Column(String(500))
    description = Column(Text)
    
    annotations = relationship("Annotation", back_populates="symbol")


class Annotation(Base):
    """Bounding box annotation on a page."""
    __tablename__ = "annotations"
    
    id = Column(Integer, primary_key=True, index=True)
    page_id = Column(Integer, ForeignKey("pages.id"), nullable=False)
    symbol_id = Column(Integer, ForeignKey("symbols.id"))
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    width = Column(Float, nullable=False)
    height = Column(Float, nullable=False)
    tag_id = Column(String(50))  # e.g., "FIC-101"
    attributes = Column(JSON, default=dict)
    confidence = Column(Float)  # AI confidence score if auto-detected
    source = Column(String(20), default="manual")  # manual, yolo, aws
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    page = relationship("Page", back_populates="annotations")
    symbol = relationship("Symbol", back_populates="annotations")
    created_by_user = relationship("User", back_populates="annotations")
    connections_from = relationship("Connection", foreign_keys="Connection.from_annotation_id", back_populates="from_annotation")
    connections_to = relationship("Connection", foreign_keys="Connection.to_annotation_id", back_populates="to_annotation")


class Connection(Base):
    """Connection/edge between two annotations."""
    __tablename__ = "connections"
    
    id = Column(Integer, primary_key=True, index=True)
    page_id = Column(Integer, ForeignKey("pages.id"), nullable=False)
    from_annotation_id = Column(Integer, ForeignKey("annotations.id"), nullable=False)
    to_annotation_id = Column(Integer, ForeignKey("annotations.id"), nullable=False)
    line_type = Column(String(50), default="process")  # process, signal, instrument
    waypoints = Column(JSON, default=list)  # List of {x, y} points
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    page = relationship("Page", back_populates="connections")
    from_annotation = relationship("Annotation", foreign_keys=[from_annotation_id], back_populates="connections_from")
    to_annotation = relationship("Annotation", foreign_keys=[to_annotation_id], back_populates="connections_to")
