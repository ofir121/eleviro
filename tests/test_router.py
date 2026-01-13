from app.routers.job_router import apply_suggestions_to_text
from app.models.suggestions import ResumeSuggestion

def test_apply_suggestions_to_text_basic():
    original = "This is a test sentence."
    suggestion = ResumeSuggestion(
        id=1,
        original_text="test sentence",
        suggested_text="awesome sentence",
        reason="Better",
        section="Summary",
        priority="high"
    )
    result = apply_suggestions_to_text(original, [suggestion])
    assert result == "This is a awesome sentence."

def test_apply_suggestions_to_text_deletion():
    original = "This is a test sentence."
    suggestion = ResumeSuggestion(
        id=1,
        original_text="test",
        suggested_text="",
        reason="Remove",
        section="Summary",
        priority="low"
    )
    result = apply_suggestions_to_text(original, [suggestion])
    # The function logic replaces with empty string, check behavior
    assert "This is a  sentence." in result

def test_apply_suggestions_multiple():
    original = "One. Two. Three."
    s1 = ResumeSuggestion(id=1, original_text="One", suggested_text="1", reason="r", section="s", priority="medium")
    s2 = ResumeSuggestion(id=2, original_text="Three", suggested_text="3", reason="r", section="s", priority="medium")
    result = apply_suggestions_to_text(original, [s1, s2])
    assert result == "1. Two. 3."

def test_apply_changes_endpoint(client):
    # Mock request data for /apply-changes
    payload = {
        "original_resume": "I have skills in Python.",
        "all_suggestions": [
            {
                "id": 10,
                "original_text": "skills in Python",
                "suggested_text": "expertise in Python",
                "reason": "Stronger",
                "section": "Skills",
                "priority": "high"
            }
        ],
        "accepted_suggestion_ids": [10]
    }
    response = client.post("/api/apply-changes", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["modified_resume"] == "I have expertise in Python."
    assert data["replacements_made"] == 1
