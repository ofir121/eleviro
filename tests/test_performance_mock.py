import pytest
import asyncio
import time
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import UploadFile
from app.services import ai_service

# ParsedResume-like object for resume_text path (multiple sections so AI is not required)
def _mock_parsed_resume():
    return MagicMock(
        full_text="Resume Content",
        preamble="Name Contact",
        sections={"experience": "Job at Co.", "education": "BS CS."},
    )

def _mock_extracted_contact():
    return MagicMock(phones=[], emails=[], location=None, linkedin_urls=[], portfolio_urls=[], other_urls=[])

@pytest.mark.asyncio
async def test_process_job_concurrency():
    """
    Verify that process_job runs tasks concurrently.
    We mock AI service calls with delays and check total execution time.
    """
    
    # Setup Mocks with specific delays
    async def fast_delay(*args, **kwargs):
        await asyncio.sleep(0.5)
        return "Done"

    async def fast_delay_json(*args, **kwargs):
        await asyncio.sleep(0.5)
        return '{"key": "value", "job_type": "Engineer", "company_name": "TestCorp"}'

    # Mock ai_service methods
    ai_service.summarize_job = AsyncMock(side_effect=fast_delay)
    ai_service.research_company = AsyncMock(side_effect=fast_delay_json)
    ai_service.format_resume = AsyncMock(side_effect=fast_delay)
    ai_service.suggest_resume_changes = AsyncMock(side_effect=fast_delay_json) # returns json structure
    ai_service.generate_cover_letter = AsyncMock(side_effect=fast_delay)
    ai_service.extract_candidate_info = AsyncMock(side_effect=fast_delay_json)
    ai_service.find_recruiters = AsyncMock(side_effect=fast_delay) # returns string/json
    ai_service.suggest_bold_changes = AsyncMock(side_effect=lambda *args, **kwargs: [{"original_text": "foo", "suggested_text": "bar"}]) # returns list directly? Check signature.
    # Check signature: suggest_bold_changes returns list. AsyncMock returns a coroutine. 
    # Logic: asyncio.sleep(0.5) then return list.
    async def bold_delay(*args, **kwargs):
        await asyncio.sleep(0.5)
        return [{"original_text": "foo", "suggested_text": "bar"}]
    ai_service.suggest_bold_changes = AsyncMock(side_effect=bold_delay)

    # Patch parsers in job_router so we don't replace the real module (which would break other tests)
    import app.routers.job_router as job_router
    mock_parsers = MagicMock()
    mock_parsers.scrape_url = MagicMock(return_value="Job Description")
    mock_parsers.parse_pdf = AsyncMock(return_value=_mock_parsed_resume())
    mock_parsers.parse_docx = AsyncMock(return_value=_mock_parsed_resume())
    mock_parsers.parse_resume_text_to_structure = MagicMock(return_value=_mock_parsed_resume())
    mock_parsers.extract_contact_from_text = MagicMock(return_value=_mock_extracted_contact())
    mock_parsers.should_use_ai_sections = MagicMock(return_value=False)
    mock_parsers.validate_resume_sections = MagicMock(
        return_value=MagicMock(
            sections_found=["experience", "education", "skills"],
            sections_missing=[],
            optional_missing=[],
            has_preamble=True,
            is_valid=True,
            warnings=[],
        )
    )

    with patch.object(job_router, "parsers", mock_parsers), patch.object(job_router, "should_use_ai_sections", return_value=False):
        start_time = time.time()

        result = await job_router.process_job(
            job_url="http://test.com",
            resume_text="Resume Content",
            is_testing_mode=True,
            bold_keywords=True,
        )

    end_time = time.time()
    duration = end_time - start_time
    
    print(f"Total Duration: {duration:.2f}s")
    
    # Expected Timeline (New Flow):
    # T=0: Start Summary(0.5), Research(0.5).
    # T=0: Start Format(0.5).
    # T=0.5: Format Done. Res/Sum Done.
    # T=0.5: Start Sugg(0.5), Cover(0.5), Info(0.5), Recruiter(0.5), Bolding(0.5).
    # T=1.0: All Done.
    # Total approx 1.0s. (Maybe slightly more due to overhead)
    
    # Expected Timeline (Old Flow - Approximate):
    # T=0: Format(0.5).
    # T=0.5: Start Res(0.5), Sum(0.5)...
    # T=1.0: End Res. Start Recruiter(0.5).
    # T=1.5: End Recruiter. Wait All.
    # T=1.5: End All. Start Bolding(0.5) (Sequential).
    # T=2.0: End.
    
    # So we expect < 1.5s. If it was fully sequential it would be > 3s.
    
    assert duration < 1.6, f"Execution took too long ({duration:.2f}s). Expected parallel execution."
    
    # Verify outputs are present
    assert result["company_name"] == "TestCorp"
    assert result["original_resume"] == "Done" # format_resume output

