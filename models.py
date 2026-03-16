from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class UploadResponse(BaseModel):
    job_id: str
    status: str
    file_count: int
    message: str

class ProgressEvent(BaseModel):
    status: str
    progress: float = 0.0
    step: str = ""
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class DailyBlock(BaseModel):
    duration_min: int = 0
    activity: str = "Review"
    technique: str = "Active Recall"

class MemoryTechnique(BaseModel):
    name: str
    description: str

class WeekPlan(BaseModel):
    week_number: int
    theme: str
    topics: List[str]
    learning_objectives: List[str]
    study_hours: int
    difficulty: int = Field(ge=1, le=5)
    daily_schedule: Dict[str, DailyBlock]
    memory_techniques: List[MemoryTechnique]
    study_tips: List[str]
    resources: List[str]
    assignments_due: List[str]
    exam_weight: str = ""

class GlobalMemoryTechniques(BaseModel):
    spaced_repetition: Dict[str, Any] = {}
    pomodoro: Dict[str, Any] = {}
    mind_mapping: Dict[str, Any] = {}
    feynman_technique: Dict[str, Any] = {}
    cornell_notes: Dict[str, Any] = {}
    active_recall: Dict[str, Any] = {}

class ExamPrep(BaseModel):
    weeks_before_exam: int = 3
    strategy: str = ""
    daily_breakdown: List[str] = []

class StudyPlan(BaseModel):
    course_name: str
    semester_duration_weeks: int = 15
    total_study_hours_per_week: int
    difficulty_level: str
    prerequisites: List[str]
    weeks: List[WeekPlan]
    global_memory_techniques: GlobalMemoryTechniques
    exam_preparation: ExamPrep
    study_environment_tips: List[str]
    productivity_hacks: List[str]
    mental_health_tips: List[str]
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class ExtractedDocument(BaseModel):
    filename: str
    total_pages: int
    text_length: int
    topics: List[str]
    raw_text: str
    metadata: Dict[str, Any]

class OrganizedContent(BaseModel):
    documents: List[ExtractedDocument]
    combined_topics: List[str]
    total_pages: int
    course_name_guess: str