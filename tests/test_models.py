import pytest
from pydantic import ValidationError
from app.models.suggestions import ResumeSuggestion, SuggestionResponse, ApplyChangesRequest

def test_resume_suggestion_valid():
    """Test creating a valid ResumeSuggestion."""
    suggestion = ResumeSuggestion(
        id=1,
        section="Skills",
        original_text="old",
        suggested_text="new",
        reason="better",
        priority="high"
    )
    assert suggestion.id == 1
    assert suggestion.priority == "high"

def test_resume_suggestion_invalid_priority():
    """Test that invalid priority raises ValidationError."""
    with pytest.raises(ValidationError):
        ResumeSuggestion(
            id=1,
            section="Skills",
            original_text="old",
            suggested_text="new",
            reason="better",
            priority="urget" # Typo/Invalid
        )

def test_resume_suggestion_missing_fields():
    """Test that missing required fields raises ValidationError."""
    with pytest.raises(ValidationError):
        ResumeSuggestion(
            id=1,
            # Missing section, original_text, etc.
            priority="high"
        )

def test_suggestion_response_valid():
    """Test creating a SuggestionResponse with a list of suggestions."""
    s1 = ResumeSuggestion(id=1, section="A", original_text="o", suggested_text="n", reason="r", priority="low")
    response = SuggestionResponse(suggestions=[s1])
    assert len(response.suggestions) == 1
    assert response.suggestions[0].priority == "low"

def test_apply_changes_request_valid():
    """Test creating a valid ApplyChangesRequest."""
    s1 = ResumeSuggestion(id=1, section="A", original_text="o", suggested_text="n", reason="r", priority="medium")
    req = ApplyChangesRequest(
        original_resume="Content",
        accepted_suggestion_ids=[1],
        all_suggestions=[s1]
    )
    assert req.original_resume == "Content"
    assert req.bold_keywords is True # Default
    assert req.is_testing_mode is True # Default

def test_apply_changes_request_defaults():
    """Test defaults in ApplyChangesRequest."""
    s1 = ResumeSuggestion(id=1, section="A", original_text="o", suggested_text="n", reason="r", priority="medium")
    req = ApplyChangesRequest(
        original_resume="Content",
        accepted_suggestion_ids=[],
        all_suggestions=[s1]
    )
    assert req.job_description == ""
