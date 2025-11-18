"""
Database Schemas for AI Tutor

Each Pydantic model represents a collection in MongoDB.
Collection name is the lowercase class name.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Dict, Any
from datetime import datetime


class Subject(BaseModel):
    user_id: str = Field(..., description="Owner user id (from Supabase)")
    name: str = Field(..., description="Subject name, e.g., Chemistry")
    description: Optional[str] = Field(None, description="Optional subject description")


class Book(BaseModel):
    user_id: str = Field(..., description="Owner user id")
    subject_id: str = Field(..., description="Subject document id")
    title: str = Field(..., description="Book title")
    original_filename: Optional[str] = Field(None, description="Uploaded file name")
    file_path: Optional[str] = Field(None, description="Server file path of the upload")
    pages: Optional[List[str]] = Field(default=None, description="Extracted text per page")
    num_pages: Optional[int] = Field(default=None, description="Number of pages extracted")


class LessonRequest(BaseModel):
    user_id: str
    subject_id: str
    book_id: str
    prompt: str = Field(..., description="User instruction for the AI tutor, e.g., 'Explain first 50 lines of Chapter 1'")
    source_mode: Literal["page_range", "lines", "chapter", "custom"] = Field("lines")
    start_page: Optional[int] = None
    end_page: Optional[int] = None
    lines: Optional[int] = Field(None, description="Number of lines to consider for 'lines' mode")


class Lesson(BaseModel):
    user_id: str
    subject_id: str
    book_id: str
    request_id: Optional[str] = None
    prompt: str
    status: Literal["pending", "processing", "complete", "error"] = "pending"
    input_excerpt: Optional[str] = None
    explanation: Optional[str] = None
    analogies: Optional[List[str]] = None
    error: Optional[str] = None
    scheduled_at: Optional[datetime] = None


class Schedule(BaseModel):
    user_id: str
    subject_id: str
    book_id: str
    prompt: str
    schedule_time_iso: str = Field(..., description="ISO datetime string for when to trigger the lesson")
    timezone: Optional[str] = Field(None, description="IANA timezone, optional")
    n8n_job_id: Optional[str] = Field(None, description="External scheduler id in n8n, if any")


class Progress(BaseModel):
    user_id: str
    subject_id: str
    book_id: str
    last_covered_page: Optional[int] = None
    last_covered_line: Optional[int] = None
    notes: Optional[str] = None


# Example user schema retained for reference but not used directly
class User(BaseModel):
    name: str
    email: str
    is_active: bool = True


class Product(BaseModel):
    title: str
    price: float
    in_stock: bool = True
