from pydantic import BaseModel
from typing import List, Literal

class ResumeSuggestion(BaseModel):
    """Individual resume change suggestion"""
    id: int
    section: str  # e.g., "Professional Summary", "Experience", "Skills"
    original_text: str
    suggested_text: str
    reason: str
    priority: Literal["high", "medium", "low"]

class SuggestionResponse(BaseModel):
    """Response containing all suggestions"""
    suggestions: List[ResumeSuggestion]

class ApplyChangesRequest(BaseModel):
    """Request to apply selected changes"""
    original_resume: str
    accepted_suggestion_ids: List[int]
    all_suggestions: List[ResumeSuggestion]
