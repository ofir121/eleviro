from pydantic import BaseModel
from typing import List, Literal, Optional

class ResumeSuggestion(BaseModel):
    """Individual resume change suggestion"""
    id: int
    section: str  # e.g., "Professional Summary", "Experience", "Skills"
    original_text: str
    suggested_text: str
    reason: str
    priority: Literal["high", "medium", "low"]
    # Phase 4.2: "first" = replace one occurrence (default), "all" = replace every match
    apply_to: Literal["first", "all"] = "first"
    # Phase 4.3: optional context string before the match (e.g. previous line) to disambiguate
    context_before: Optional[str] = None

class SuggestionResponse(BaseModel):
    """Response containing all suggestions"""
    suggestions: List[ResumeSuggestion]

class ApplyChangesRequest(BaseModel):
    """Request to apply selected changes"""
    original_resume: str
    accepted_suggestion_ids: List[int]
    all_suggestions: List[ResumeSuggestion]
    bold_keywords: bool = True
    job_description: str = ""
    is_testing_mode: bool = True
