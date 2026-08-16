import asyncio
from app.utils.parsers import ExtractedContact, ParsedResume
from app.utils.formatters import build_markdown_resume

text = """Ofir Shliefer
Gaithersburg, MD · 973-800-9119 · ofir.shliefer@gmail.com
Accomplished data professional with over 7 years of experience in statistical data analysis, architecting robust ETL pipelines, and productionizing machine learning models.

Machine Learning Engineer, Welldoc, Columbia, MD, USA | FEB 2026 – PRESENT
Designed, implemented, and deployed a production batch inference pipeline
Built and maintained a feature store pipeline"""

res = ParsedResume(
    full_text=text,
    preamble="Ofir Shliefer\nGaithersburg, MD · 973-800-9119 · ofir.shliefer@gmail.com\nAccomplished data professional with over 7 years of experience in statistical data analysis, architecting robust ETL pipelines, and productionizing machine learning models.",
    sections={
        "experience": "Machine Learning Engineer, Welldoc, Columbia, MD, USA | FEB 2026 – PRESENT\nDesigned, implemented, and deployed a production batch inference pipeline\nBuilt and maintained a feature store pipeline"
    }
)
contact = ExtractedContact(phones=["973-800-9119"], emails=["ofir.shliefer@gmail.com"], location="Gaithersburg, MD", linkedin_urls=[], portfolio_urls=[], other_urls=[], security_clearance=None)
md = build_markdown_resume(res, contact, "Ofir Shliefer")
print(md)
