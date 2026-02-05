from fastapi import APIRouter, Form, HTTPException, UploadFile, File, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from app.services import ai_service
from app.utils import parsers, generators
from app.utils.parsers import should_use_ai_sections, validate_resume_sections, extract_contact_from_text, is_plausible_phone
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
    bold_keywords: bool = Form(True),
    use_ai_sections: bool = Form(False),
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

    # 2. Get Resume Text (as ParsedResume when possible for section-aware AI decision)
    parsed_resume = None
    if resume_text:
        parsed_resume = parsers.parse_resume_text_to_structure(resume_text)
        final_resume_text = parsed_resume.full_text
    elif resume_file and resume_file.filename:  # Check if file actually has a filename
        if resume_file.filename.endswith(".pdf"):
            parsed_resume = await parsers.parse_pdf(resume_file)
        elif resume_file.filename.endswith(".docx"):
            parsed_resume = await parsers.parse_docx(resume_file)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format. Please upload PDF or DOCX.")
        final_resume_text = parsed_resume.full_text
    else:
        raise HTTPException(status_code=400, detail="Please provide either Resume text or upload a file.")

    if not final_job_desc or not final_resume_text:
         raise HTTPException(status_code=400, detail="Could not extract text from inputs.")

    # 2.4 Validate which sections were found in the resume
    section_validation = validate_resume_sections(parsed_resume) if parsed_resume else None
    section_validation_payload = (
        {
            "sections_found": section_validation.sections_found,
            "sections_missing": section_validation.sections_missing,
            "optional_missing": section_validation.optional_missing,
            "has_preamble": section_validation.has_preamble,
            "is_valid": section_validation.is_valid,
            "warnings": section_validation.warnings,
        }
        if section_validation is not None
        else None
    )

    # 2.5 Optional: refine section structure with AI only when regex detection is weak
    # (no sections, only one section, or preamble too large)
    if use_ai_sections and parsed_resume is not None and should_use_ai_sections(parsed_resume):
        final_resume_text = await ai_service.parse_resume_sections_with_ai(
            parsed_resume.full_text,
            existing_sections=parsed_resume.sections if parsed_resume.sections else None,
            is_testing_mode=is_testing_mode,
        )

    # 3. Format Resume (Must be done before other resume tasks)
    formatted_resume_text = await ai_service.format_resume(final_resume_text, is_testing_mode)

    # Parsed contact (phone, email, location, LinkedIn, portfolio) for fallback and cover letter
    parsed_contact = extract_contact_from_text(final_resume_text)
    contact_dict = {
        "phones": parsed_contact.phones,
        "emails": parsed_contact.emails,
        "location": parsed_contact.location,
        "linkedin_urls": parsed_contact.linkedin_urls,
        "portfolio_urls": parsed_contact.portfolio_urls,
        "other_urls": parsed_contact.other_urls,
    }
    
    # 4. Start Resume-related tasks concurrently
    task_suggestions = asyncio.create_task(ai_service.suggest_resume_changes(formatted_resume_text, final_job_desc, is_testing_mode))
    task_cover = asyncio.create_task(ai_service.generate_cover_letter(
        formatted_resume_text, final_job_desc, is_testing_mode, contact=contact_dict
    ))
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

    merge_bolding_into_rewrites(resume_suggestions, bolding_suggestions_raw)

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

    # Parse Candidate Info (use parsed contact when AI returns empty)
    try:
        candidate_data = json.loads(candidate_info_json)
        raw_name = candidate_data.get("name")
        candidate_name = str(raw_name).strip().title() if raw_name else "Candidate"
        raw_email = candidate_data.get("email")
        candidate_email = str(raw_email).strip().lower() if raw_email else ""
        candidate_phone = (candidate_data.get("phone") or "").strip()
    except (json.JSONDecodeError, AttributeError):
        candidate_name = "Candidate"
        candidate_email = ""
        candidate_phone = ""

    # Reject AI phone if it looks like a date range (e.g. "July 2024 - Present" from layout/OCR confusion)
    if candidate_phone and not is_plausible_phone(candidate_phone):
        candidate_phone = ""

    if not candidate_email and parsed_contact.emails:
        candidate_email = parsed_contact.emails[0].strip().lower()
    if not candidate_phone and parsed_contact.phones:
        candidate_phone = parsed_contact.phones[0].strip()
    # Fallback: re-extract contact from formatted resume (preamble may have contact line)
    if not candidate_phone or not candidate_email:
        formatted_contact = extract_contact_from_text(formatted_resume_text)
        if not candidate_phone and formatted_contact.phones:
            candidate_phone = formatted_contact.phones[0].strip()
        if not candidate_email and formatted_contact.emails:
            candidate_email = formatted_contact.emails[0].strip().lower()
    candidate_location = (parsed_contact.location or "").strip() if parsed_contact else ""
    candidate_linkedin = (parsed_contact.linkedin_urls[0] if parsed_contact and parsed_contact.linkedin_urls else "").strip()
    candidate_portfolio = (parsed_contact.portfolio_urls[0] if parsed_contact and parsed_contact.portfolio_urls else "").strip()
    if not candidate_portfolio and parsed_contact and parsed_contact.other_urls:
        candidate_portfolio = parsed_contact.other_urls[0].strip()

    return {
        "job_summary": job_summary,
        "company_summary": company_summary,
        "company_name": company_name,
        "role_title": role_title,
        "candidate_name": candidate_name,
        "candidate_email": candidate_email,
        "candidate_phone": candidate_phone,
        "candidate_location": candidate_location,
        "candidate_linkedin": candidate_linkedin,
        "candidate_portfolio": candidate_portfolio,
        "resume_suggestions": resume_suggestions,
        "original_resume": formatted_resume_text,
        "cover_letter": cover_letter,
        "job_description": final_job_desc,
        "recruiters": recruiters_raw,
        "section_validation": section_validation_payload,
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

def _parse_markdown_sections(text: str) -> list:
    """
    Split text by ## Markdown headers. Returns list of (section_name, start, end)
    where section_name is the header line after ## (e.g. "Experience"), and
    start/end are byte positions so text[start:end] is the full section including header.
    """
    sections = []
    # Match ## Header at start of line (optional leading newline)
    for m in re.finditer(r"^##\s+([^\n]+)", text, re.MULTILINE):
        name = m.group(1).strip()
        start = m.start()
        sections.append((name, start, len(text)))
    # Set end of each section to start of next
    for i in range(len(sections) - 1):
        name, start, _ = sections[i]
        sections[i] = (name, start, sections[i + 1][1])
    return sections


def merge_bolding_into_rewrites(resume_suggestions: list, bolding_suggestions_raw: list) -> None:
    """
    Merge bolding suggestions into rewrite suggestions in-place.
    When a bolding suggestion targets the same line as a rewrite (by original_text or suggested_text),
    the rewrite's suggested_text is updated to include bold; the bolding suggestion is not added as
    a separate item, avoiding duplicate suggestions (one with bold, one without).
    """
    if not bolding_suggestions_raw or not isinstance(bolding_suggestions_raw, list):
        return
    start_id = max([s.get("id", 0) for s in resume_suggestions], default=0) + 1

    rewrite_output_map = {}
    rewrite_original_map = {}
    for s in resume_suggestions:
        rewrite_output_map[s.get("suggested_text", "").strip()] = s

    def clean_bullet(text):
        return re.sub(r"^[-*]\s+", "", text).strip()

    for s in resume_suggestions:
        orig = clean_bullet(s.get("original_text", ""))
        if orig and orig not in rewrite_original_map:
            rewrite_original_map[orig] = s

    for i, bold_s in enumerate(bolding_suggestions_raw):
        bold_orig = bold_s.get("original_text", "").strip()
        bold_suggested = bold_s.get("suggested_text", "").strip()
        clean_bold_orig = clean_bullet(bold_orig)

        match = rewrite_output_map.get(bold_orig)
        if not match:
            match = rewrite_output_map.get(clean_bold_orig)
        if not match:
            for rewrite_text, rewrite_s in rewrite_output_map.items():
                if rewrite_text and (rewrite_text in bold_orig or bold_orig in rewrite_text):
                    match = rewrite_s
                    break
        if not match:
            match = rewrite_original_map.get(clean_bold_orig)
            if not match and clean_bold_orig:
                match = rewrite_original_map.get(bold_orig)

        if match:
            rewrite_has_bullet = match["suggested_text"].strip().startswith(("-", "*"))
            bold_has_bullet = bold_suggested.startswith(("-", "*"))
            if match.get("suggested_text", "").strip() in (bold_orig, clean_bold_orig):
                final_text = bold_suggested
                if bold_has_bullet and not rewrite_has_bullet:
                    final_text = clean_bullet(bold_suggested)
                match["suggested_text"] = final_text
            else:
                final_text = _apply_bolding_pattern(bold_suggested, match["suggested_text"])
                match["suggested_text"] = final_text
        else:
            bold_s["id"] = start_id + i
            resume_suggestions.append(bold_s)


def _apply_bolding_pattern(bold_suggested: str, rewrite_suggested: str) -> str:
    """
    Apply the bolding pattern from bold_suggested (markdown with **) to rewrite_suggested.
    Uses word-position alignment: same word indices that are bolded in the original get bolded
    in the rewrite (e.g. so "20%" -> "25%" still gets bolded).
    """
    content_no_bold = re.sub(r"\*\*", "", bold_suggested).strip()
    words_orig = content_no_bold.split()
    if not words_orig:
        return rewrite_suggested
    bold_indices = set()
    pos = 0
    for m in re.finditer(r"\*\*([^*]+)\*\*", bold_suggested):
        phrase = m.group(1).strip()
        if not phrase:
            continue
        idx = content_no_bold.find(phrase, pos)
        if idx < 0:
            continue
        start_word = len(content_no_bold[:idx].split())
        n_words = len(phrase.split())
        for i in range(start_word, min(start_word + n_words, len(words_orig))):
            bold_indices.add(i)
        pos = idx + len(phrase)
    words_rewrite = rewrite_suggested.split()
    n = min(len(words_rewrite), len(words_orig))
    parts = []
    for i in range(len(words_rewrite)):
        if i < n and i in bold_indices:
            parts.append("**" + words_rewrite[i] + "**")
        else:
            parts.append(words_rewrite[i])
    return " ".join(parts)


def _section_name_matches(suggestion_section: str, header_name: str) -> bool:
    """True if suggestion's section hint matches the markdown header (case-insensitive, normalize)."""
    if not (suggestion_section and header_name):
        return False
    a = re.sub(r"\s+", " ", suggestion_section.strip().lower())
    b = re.sub(r"\s+", " ", header_name.strip().lower())
    return a == b or a in b or b in a


def _normalize_whitespace(s: str) -> str:
    """Collapse whitespace for anchor/context comparison."""
    return " ".join((s or "").split())


def apply_suggestions_to_text(original_text: str, suggestions: list) -> str:
    """
    Apply a list of suggestions (dict or Pydantic) to the resume text.

    Behavior:
    - Section-aware: when the resume has ## Section headers and a suggestion has
      section, replacement is restricted to that section (fallback: full text).
    - apply_to "first" (default): replace one occurrence; "all": replace every match.
    - context_before: optional anchor; only matches preceded by this context are replaced.
    - Replacements are applied in reverse order of position to preserve indices.
    - Empty suggested_text is treated as deletion.
    """
    modified_text = original_text
    md_sections = _parse_markdown_sections(original_text)
    replacements = []

    for s in suggestions:
        orig = s.get("original_text") if isinstance(s, dict) else s.original_text
        new_val = s.get("suggested_text") if isinstance(s, dict) else s.suggested_text
        section_hint = s.get("section") if isinstance(s, dict) else getattr(s, "section", None)
        apply_to = s.get("apply_to", "first") if isinstance(s, dict) else getattr(s, "apply_to", "first")
        context_before = s.get("context_before") if isinstance(s, dict) else getattr(s, "context_before", None)
        if not orig:
            continue

        parts = re.split(r"\s+", orig.strip())
        parts = [re.escape(p) for p in parts if p]
        pattern = r"\s+".join(parts)

        search_text = original_text
        section_start_offset = 0
        if section_hint and md_sections:
            for name, start, end in md_sections:
                if _section_name_matches(section_hint, name):
                    search_text = original_text[start:end]
                    section_start_offset = start
                    break

        anchor_norm = _normalize_whitespace(context_before) if context_before else None
        matches = list(re.finditer(pattern, search_text, re.IGNORECASE))
        if anchor_norm:
            matches = [
                m for m in matches
                if anchor_norm in _normalize_whitespace(search_text[max(0, m.start() - 200) : m.start()])
            ]
        if apply_to == "first" and matches:
            matches = matches[:1]
        for match in matches:
            global_start = section_start_offset + match.start()
            global_end = section_start_offset + match.end()
            replacements.append((global_start, global_end, new_val or ""))

    replacements.sort(key=lambda x: x[0], reverse=True)
    for start, end, new_val in replacements:
        modified_text = modified_text[:start] + new_val + modified_text[end:]
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
