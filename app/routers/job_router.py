from fastapi import APIRouter, Form, HTTPException, UploadFile, File, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from app.services import ai_service
from app.utils import parsers, generators
from app.models.suggestions import ResumeSuggestion, SuggestionResponse, ApplyChangesRequest
import io
import json
import re
import asyncio

router = APIRouter(
    prefix="/api",
    tags=["job"]
)

@router.post("/process-job")
async def process_job(
    job_description: Optional[str] = Form(None),
    job_url: Optional[str] = Form(None),
    resume_text: Optional[str] = Form(None),
    resume_file: Optional[UploadFile] = File(None),
    is_testing_mode: bool = Form(True)
):
    # 1. Get Job Description
    final_job_desc = ""
    if job_url:
        final_job_desc = parsers.scrape_url(job_url)
        if not final_job_desc:
            raise HTTPException(status_code=400, detail="Could not scrape job description from URL.")
    elif job_description:
        final_job_desc = job_description
    else:
        raise HTTPException(status_code=400, detail="Please provide either a Job Description text or URL.")

    # 2. Get Resume Text
    final_resume_text = ""
    if resume_text:
        final_resume_text = resume_text
    elif resume_file and resume_file.filename:  # Check if file actually has a filename
        if resume_file.filename.endswith(".pdf"):
            final_resume_text = await parsers.parse_pdf(resume_file)
        elif resume_file.filename.endswith(".docx"):
            final_resume_text = await parsers.parse_docx(resume_file)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format. Please upload PDF or DOCX.")
    else:
        raise HTTPException(status_code=400, detail="Please provide either Resume text or upload a file.")

    if not final_job_desc or not final_resume_text:
         raise HTTPException(status_code=400, detail="Could not extract text from inputs.")

    # First, format the resume to get a clean markdown version
    # This needs to run first because suggest_resume_changes needs to match against this text
    formatted_resume_text = await ai_service.format_resume(final_resume_text, is_testing_mode)
    
    # Now run remaining AI tasks concurrently
    # Use formatted_resume_text for suggestions so original_text matches what we'll display/download
    results = await asyncio.gather(
        ai_service.summarize_job(final_job_desc, is_testing_mode),
        ai_service.summarize_company(final_job_desc, is_testing_mode),
        ai_service.suggest_resume_changes(formatted_resume_text, final_job_desc, is_testing_mode),
        ai_service.generate_cover_letter(formatted_resume_text, final_job_desc, is_testing_mode)
    )

    job_summary, company_summary, resume_suggestions_json, cover_letter = results
    
    # Parse JSON response
    try:
        suggestions_data = json.loads(resume_suggestions_json)
        resume_suggestions = suggestions_data.get("suggestions", [])
    except json.JSONDecodeError as e:
        print(f"Error parsing suggestions JSON: {e}")
        print(f"Raw response: {resume_suggestions_json}")
        # Fallback to empty suggestions if parsing fails
        resume_suggestions = []

    return {
        "job_summary": job_summary,
        "company_summary": company_summary,
        "resume_suggestions": resume_suggestions,
        "original_resume": formatted_resume_text,  # Use formatted version
        "cover_letter": cover_letter
    }

@router.post("/download")
async def download_document(
    content: str = Form(...),
    filename: str = Form(...)
):
    file_stream = generators.create_docx(content)
    return StreamingResponse(
        file_stream,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}.docx"'}
    )

@router.post("/apply-changes")
async def apply_changes(request: ApplyChangesRequest):
    """
    Apply selected resume suggestions to the original resume text.
    """
    modified_resume = request.original_resume
    
    # Create a mapping of suggestion IDs to suggestions
    suggestions_dict = {s.id: s for s in request.all_suggestions}
    
    # Get only the accepted suggestions
    accepted_suggestions = [
        suggestions_dict[sid] for sid in request.accepted_suggestion_ids 
        if sid in suggestions_dict
    ]
    
    # Sort by position in text (to avoid replacement conflicts)
    # Find each original_text position and sort
    suggestions_with_pos = []
    for suggestion in accepted_suggestions:
        # Use regex to handle whitespace variations
        pattern = re.escape(suggestion.original_text)
        pattern = re.sub(r'\\\s+', r'\\s+', pattern)  # Allow flexible whitespace
        
        match = re.search(pattern, modified_resume, re.IGNORECASE)
        if match:
            suggestions_with_pos.append((match.start(), suggestion))
    
    # Sort by position (descending) to avoid index shifting
    suggestions_with_pos.sort(key=lambda x: x[0], reverse=True)
    
    # Apply replacements
    replacements_made = 0
    for pos, suggestion in suggestions_with_pos:
        # Use regex for more flexible matching
        pattern = re.escape(suggestion.original_text)
        pattern = re.sub(r'\\\s+', r'\\s+', pattern)
        
        # Replace only the first occurrence (which should be at the position we found)
        # If suggested_text is empty (deletion), remove the entire bullet point line
        if not suggestion.suggested_text.strip():
            full_line_pattern = r'^\s*[-*]\s*' + pattern + r'\s*$'
            new_resume, count = re.subn(full_line_pattern, '', modified_resume, count=1, flags=re.IGNORECASE | re.MULTILINE)
            if count > 0:
                modified_resume = new_resume
            else:
                modified_resume = re.sub(pattern, '', modified_resume, count=1, flags=re.IGNORECASE)
        else:
            modified_resume = re.sub(
                pattern, 
                suggestion.suggested_text, 
                modified_resume, 
                count=1,
                flags=re.IGNORECASE
            )
        replacements_made += 1
    
    return {
        "modified_resume": modified_resume,
        "replacements_made": replacements_made,
        "total_accepted": len(request.accepted_suggestion_ids)
    }

