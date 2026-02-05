from app.routers.job_router import apply_suggestions_to_text
from app.models.suggestions import ResumeSuggestion
from app.utils.parsers import is_plausible_phone, extract_contact_from_text, ExtractedContact

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

def test_candidate_phone_rejects_date_range_and_uses_parsed_fallback():
    """
    When AI returns a date range as phone (e.g. 'July 2024 - Present'), we reject it
    and use the parsed contact phone from the resume text instead.
    """
    # Simulate AI returning the buggy value (layout/OCR confusion)
    candidate_phone = "July 2024 - Present"
    parsed_contact = ExtractedContact(
        phones=["(555) 123-4567"],
        emails=["candidate@example.com"],
        linkedin_urls=[],
        portfolio_urls=[],
        other_urls=[],
        location="Anytown, ST",
    )
    # Same logic as job_router.process_job
    if candidate_phone and not is_plausible_phone(candidate_phone):
        candidate_phone = ""
    if not candidate_phone and parsed_contact.phones:
        candidate_phone = parsed_contact.phones[0].strip()
    assert candidate_phone == "(555) 123-4567"
    assert "July" not in candidate_phone and "Present" not in candidate_phone


def test_candidate_phone_from_extracted_resume_text():
    """Resume text with a real phone should yield that phone from extract_contact_from_text."""
    text = "Jane Doe\nAnytown, ST\n(555) 111-2222\ncandidate@example.com\nJuly 2024 - Present"
    contact = extract_contact_from_text(text)
    assert any("555" in p for p in contact.phones)
    assert not any("July" in p or "Present" in p for p in contact.phones)
    assert is_plausible_phone(contact.phones[0])


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
