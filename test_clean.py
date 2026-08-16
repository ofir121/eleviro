from app.utils.parsers import clean_resume_text

text = """
Machine Learning Engineer, Welldoc, Columbia, MD, USA | FEB 2026 – PRESENT
Designed, implemented, and deployed a production batch inference pipeline on databricks serving 100K+ daily users.
Built and maintained a feature store pipeline processing dozens of features daily.

Programming Languages: 
Python, Matlab, R, C, C++, SQL
ML & Data Science: 
LLMs, Transformers, NLP
"""

print(clean_resume_text(text))
