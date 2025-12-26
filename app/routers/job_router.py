from fastapi import APIRouter, Form, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from app.services import ai_service
from app.utils import parsers, generators
import io

router = APIRouter(
    prefix="/api",
    tags=["job"]
)

@router.post("/process-job")
async def process_job(
    job_description: Optional[str] = Form(None),
    job_url: Optional[str] = Form(None),
    resume_text: Optional[str] = Form(None),
    resume_file: Optional[UploadFile] = File(None)
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
    if resume_file:
        if resume_file.filename.endswith(".pdf"):
            final_resume_text = await parsers.parse_pdf(resume_file)
        elif resume_file.filename.endswith(".docx"):
            final_resume_text = await parsers.parse_docx(resume_file)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format. Please upload PDF or DOCX.")
    elif resume_text:
        final_resume_text = resume_text
    else:
        raise HTTPException(status_code=400, detail="Please provide either Resume text or upload a file.")

    if not final_job_desc or not final_resume_text:
         raise HTTPException(status_code=400, detail="Could not extract text from inputs.")

    # Run AI tasks
    job_summary = ai_service.summarize_job(final_job_desc)
    company_summary = ai_service.summarize_company(final_job_desc)
    adapted_resume = ai_service.adapt_resume(final_resume_text, final_job_desc)
    cover_letter = ai_service.generate_cover_letter(final_resume_text, final_job_desc)

    return {
        "job_summary": job_summary,
        "company_summary": company_summary,
        "adapted_resume": adapted_resume,
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
        headers={"Content-Disposition": f"attachment; filename={filename}.docx"}
    )
