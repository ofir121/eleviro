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
    is_testing_mode: bool = Form(True),
    bold_keywords: bool = Form(True)
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

    # [OPTIMIZATION] Start Job-related tasks immediately (don't wait for resume parsing)
    task_summary = asyncio.create_task(ai_service.summarize_job(final_job_desc, is_testing_mode))
    task_research = asyncio.create_task(ai_service.research_company(final_job_desc, is_testing_mode))

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

    # 3. Format Resume (Must be done before other resume tasks)
    formatted_resume_text = await ai_service.format_resume(final_resume_text, is_testing_mode)
    
    # 4. Start Resume-related tasks concurrently
    task_suggestions = asyncio.create_task(ai_service.suggest_resume_changes(formatted_resume_text, final_job_desc, is_testing_mode))
    task_cover = asyncio.create_task(ai_service.generate_cover_letter(formatted_resume_text, final_job_desc, is_testing_mode))
    task_info = asyncio.create_task(ai_service.extract_candidate_info(formatted_resume_text, is_testing_mode))

    # 5. Get Research Results (needed for Job Type & Recruiters)
    # We await this now so we can start dependent tasks
    try:
        company_research_json = await task_research
        company_data = json.loads(company_research_json)
        job_type = company_data.get("job_type", "General Role")
        company_name_extracted = company_data.get("company_name", "")
    except Exception as e:
        print(f"Error getting job type/company name: {e}")
        company_research_json = "{}" # Fallback
        job_type = "General Role"
        company_name_extracted = ""

    # 6. Start Dependent Tasks (Recruiters & Bolding)
    
    # Recruiter Search
    task_recruiters = asyncio.create_task(ai_service.find_recruiters(company_name_extracted, job_description=final_job_desc, is_testing_mode=is_testing_mode))

    # Bolding (Now runs in parallel with Suggestions!)
    if bold_keywords:
        # Note: We run bolding on formatted_resume_text. Currently we do NOT wait for rewrites.
        # The merging logic handles applying these bold matches to rewritten text if needed.
        task_bolding = asyncio.create_task(ai_service.suggest_bold_changes(formatted_resume_text, final_job_desc, job_type, is_testing_mode))
    else:
        task_bolding = asyncio.create_task(asyncio.sleep(0, result=[]))

    # 7. Await All Remaining Tasks
    job_summary = await task_summary
    candidate_info_json = await task_info
    resume_suggestions_json = await task_suggestions
    cover_letter = await task_cover
    bolding_suggestions_raw = await task_bolding
    recruiters_raw = await task_recruiters
    
    # Parse Rewrite Suggestions
    try:
        suggestions_data = json.loads(resume_suggestions_json)
        resume_suggestions = suggestions_data.get("suggestions", [])
    except json.JSONDecodeError as e:
        print(f"Error parsing suggestions JSON: {e}")
        resume_suggestions = []

    # [REMOVED] Redundant "Virtual Resume" creation and sequential bolding call.
    # We now trust the parallel bolding result and the merging logic.

    # Merge Bolding into Rewrites
    # Logic:
    # 1. Start IDs after rewrites
    start_id = max([s.get("id", 0) for s in resume_suggestions], default=0) + 1
    
    # 2. Create a map of {suggested_text: suggestion_object} from REWRITES
    # We map the OUTPUT text of the rewrite to the suggestion object
    rewrite_output_map = {}
    for s in resume_suggestions:
        rewrite_output_map[s.get("suggested_text", "").strip()] = s

    # Helper for loose matching
    def clean_bullet(text):
        return re.sub(r'^[-*]\s+', '', text).strip()

    if bolding_suggestions_raw and isinstance(bolding_suggestions_raw, list):
        for i, bold_s in enumerate(bolding_suggestions_raw):
            bold_orig = bold_s.get("original_text", "").strip()
            bold_suggested = bold_s.get("suggested_text", "").strip()
            
            # Try 1: Exact Match of Output Text (Unlikely if it was rewritten, but check if user didn't change it)
            match = rewrite_output_map.get(bold_orig)
            
            # Try 2: Loose Match (ignore bullets)
            if not match:
                clean_bold_orig = clean_bullet(bold_orig)
                match = rewrite_output_map.get(clean_bold_orig)
            
            # Try 3: Check if Rewrite output is a substring of Bolding input (or vice versa)
            if not match:
                for rewrite_text, rewrite_s in rewrite_output_map.items():
                    if rewrite_text and (rewrite_text in bold_orig or bold_orig in rewrite_text):
                        match = rewrite_s
                        break
            
            if match:
                # MATCH FOUND: The bolding suggestion targets a line that was just rewritten
                
                # Careful Update: We need to preserve the bullet-less nature of the rewrite if it was bullet-less.
                rewrite_has_bullet = match['suggested_text'].strip().startswith(('-', '*'))
                bold_has_bullet = bold_suggested.startswith(('-', '*'))
                
                final_text = bold_suggested
                if bold_has_bullet and not rewrite_has_bullet:
                    final_text = clean_bullet(bold_suggested)
                
                match["suggested_text"] = final_text
            else:
                # NO MATCH: This is a standalone bolding suggestion
                bold_s["id"] = start_id + i
                resume_suggestions.append(bold_s)

    # Parse Company Research
    try:
        company_data = json.loads(company_research_json)
        company_summary = company_data.get("company_summary_markdown", "No summary available.")
        company_name = company_data.get("company_name", "Company")
        role_title = company_data.get("role_title", "Role")
    except json.JSONDecodeError:
        company_summary = "Error parsing company research."
        company_name = "Company"
        role_title = "Role"

    # Parse Candidate Info
    try:
        candidate_data = json.loads(candidate_info_json)
        # Handle potential None values if key exists but is null
        raw_name = candidate_data.get("name")
        candidate_name = str(raw_name).strip().title() if raw_name else "Candidate"
        
        raw_email = candidate_data.get("email")
        candidate_email = str(raw_email).strip().lower() if raw_email else ""
        
        candidate_phone = candidate_data.get("phone", "")
    except (json.JSONDecodeError, AttributeError):
        candidate_name = "Candidate"
        candidate_email = ""
        candidate_phone = ""

    return {
        "job_summary": job_summary,
        "company_summary": company_summary,
        "company_name": company_name,
        "role_title": role_title,
        "candidate_name": candidate_name,
        "candidate_email": candidate_email,
        "candidate_phone": candidate_phone,
        "resume_suggestions": resume_suggestions,
        "original_resume": formatted_resume_text,
        "cover_letter": cover_letter,
        "job_description": final_job_desc,
        "recruiters": recruiters_raw
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

def apply_suggestions_to_text(original_text: str, suggestions: list) -> str:
    """Helper to apply a list of suggestions (dict or obj) to text."""
    modified_text = original_text
    
    # Sort by position in text to avoid conflicts
    # Since we don't have positions in the dict, we search
    suggestions_with_pos = []
    
    for s in suggestions:
        # data might be dict or Pydantic object
        orig = s.get("original_text") if isinstance(s, dict) else s.original_text
        new_val = s.get("suggested_text") if isinstance(s, dict) else s.suggested_text
        
        if not orig: continue

        # ROBUST STRATEGY: Split by whitespace, escape parts, join with \s+
        # This ensures that any sequence of whitespace in the suggestion matches
        # any sequence of whitespace (newline, space, tab) in the resume.
        parts = re.split(r'\s+', orig.strip())
        parts = [re.escape(p) for p in parts if p]
        pattern = r'\s+'.join(parts)
        
        match = re.search(pattern, modified_text, re.IGNORECASE)
        if match:
            suggestions_with_pos.append((match.start(), pattern, new_val))

    # Sort descending
    suggestions_with_pos.sort(key=lambda x: x[0], reverse=True)
    
    for _, pattern, new_val in suggestions_with_pos:
        if not new_val.strip():
             # Deletion
             # Try to remove the full line bullet if possible
             full_line_pattern = r'^\s*[-*]\s*' + pattern + r'\s*$'
             res, count = re.subn(full_line_pattern, '', modified_text, count=1, flags=re.IGNORECASE | re.MULTILINE)
             if count == 0:
                 modified_text = re.sub(pattern, '', modified_text, count=1, flags=re.IGNORECASE)
             else:
                 modified_text = res
        else:
            modified_text = re.sub(pattern, new_val, modified_text, count=1, flags=re.IGNORECASE)
            
    return modified_text

@router.post("/apply-changes")
async def apply_changes(request: ApplyChangesRequest):
    """
    Apply selected resume suggestions to the original resume text.
    """
    # Reuse the helper logic but adapt to input format
    # The helper works on raw dicts/objects with 'original_text' and 'suggested_text'
    # request.all_suggestions contains Pydantic models
    
    suggestions_map = {s.id: s for s in request.all_suggestions}
    accepted_list = [suggestions_map[sid] for sid in request.accepted_suggestion_ids if sid in suggestions_map]
    
    modified_resume = apply_suggestions_to_text(request.original_resume, accepted_list)
    
    return {
        "modified_resume": modified_resume,
        "replacements_made": len(accepted_list),
        "total_accepted": len(request.accepted_suggestion_ids)
    }




class OutreachRequest(BaseModel):
    resume_text: str
    job_description: str
    outreach_type: str
    is_testing_mode: bool = True
    company_name: str = "the company"
    role_title: str = "the role"

@router.post("/generate-outreach")
async def generate_outreach_endpoint(request: OutreachRequest):
    content = await ai_service.generate_outreach(
        request.resume_text, 
        request.job_description, 
        request.outreach_type, 
        request.is_testing_mode,
        request.company_name,
        request.role_title
    )
    return {"content": content}
