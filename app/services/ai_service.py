import os
import re
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
client = AsyncOpenAI(api_key=api_key) if api_key else None
reasoning_model = "gpt-5-mini"
writing_model = "gpt-3.5-turbo" #"gpt-4.1-mini"
TESTING_MODEL = "gpt-3.5-turbo"

def clean_newlines(text: str) -> str:
    """Remove excessive consecutive newlines, keeping at most one blank line."""
    return re.sub(r'\n{3,}', '\n\n', text.strip())

async def get_completion(prompt: str, model: str = writing_model, **kwargs):
    if not client:
        return "Error: OPENAI_API_KEY not found. Please set it in the .env file."
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            **kwargs
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        return "Error generating content. Please check your API key and try again."

async def summarize_job(job_description: str, is_testing_mode: bool = False) -> str:
    model = TESTING_MODEL if is_testing_mode else writing_model
    prompt = f"""
    Please summarize the following job description. Format the output using Markdown.
    Output ONLY the markdown content. Do not include any introductory or concluding text.
    Structure the summary with the following sections:
    
    ## Role Overview
    (A brief paragraph describing the role)

    ## Required Skills & Qualifications
    (A bulleted list of the required skills and qualifications)
    
    Job Description:
    {job_description}
    """
    return await get_completion(prompt, model=model)

async def summarize_company(job_description: str, is_testing_mode: bool = False) -> str:
    model = TESTING_MODEL if is_testing_mode else writing_model
    prompt = f"""
    Based on the following job description, summarize what the company does. Format the output using Markdown.
    Output ONLY the markdown content. Do not include any introductory or concluding text.
    Structure the summary with the following sections if the information is available or can be inferred:
    
    ## Company Mission
    (A brief overview of the company's mission and what they do)

    ## Industry & Products
    (Details about the industry they operate in and their key products/services)

    ## Culture & Values
    (Any information about the company culture or values mentioned)
    
    Job Description:
    {job_description}
    """
    return await get_completion(prompt, model=model)

async def adapt_resume(resume_text: str, job_description: str, is_testing_mode: bool = False) -> str:
    model = TESTING_MODEL if is_testing_mode else writing_model
    prompt = f"""
    # Role
    You are an expert Career Coach and Resume Writer. Your goal is to adapt a candidate's resume to perfectly match a specific job description.

    # Task
    Adapt the provided resume to better match the job description.
    
    # Constraints
    - Output ONLY the markdown content.
    - Do not include any introductory or concluding text.
    - The adapted resume MUST NOT exceed 2 pages.
    - Do NOT use tables or code blocks.
    - CRITICAL: NEVER put bullet points (- or *) before any headline line. A headline is any line containing | (pipe), such as Role | Date or Degree | Date. Only content UNDER headlines should have bullet points.
    - CRITICAL: Include ALL experiences and education from the original resume. NEVER use "..." or ellipsis to skip content. Do NOT abbreviate or omit any entries.
    - CRITICAL: Do NOT include a section for "Extracted Links" or list URLs at the end of the resume. Only include links if they were part of the contact info or body text in the original resume.

    # Formatting Rules
    1. **Name**: Use # for the Name. Bold and center it.
    2. **Contact Info**: Place contact details (location, phone, email, work authorization) on a single line directly below the name, separated by · (middle dot). Only include if present in the original resume.
       - Example: Baltimore, MD · XXX-XXX-XXXX · email@example.com · U.S. Permanent Residence
    3. **Section Headers**: Use ## for headers (Experience, Education, Skills). Bold them.
    4. **Experience Entries**:
       - Format: **Role**, Location | Date Range
       - Example: **Software Engineer**, New York | Jan 2020 - Present
       - If Location is missing: **Role** | Date Range
       - If Location is missing: **Role** | Date Range
       - CRITICAL: Do NOT put a bullet point (neither - nor *) before the Role line.
       - WRONG: - **Software Engineer**, New York | Jan 2020 - Present
       - RIGHT: **Software Engineer**, New York | Jan 2020 - Present
    5. **Bullet Points**:
       - Each bullet point MUST start with a bolded headline or key phrase followed by a colon.
       - Example: **Project Management**: Led a team of 5 developers...
    6. **Education**:
       - Format: **Degree**, [School Name] | [Start Date - End Date]
       - CRITICAL: Do NOT put a bullet point (neither - nor *) before the Degree line.
       - WRONG: - **Bachelor of Science**, University of X | 2010 - 2014
       - RIGHT: **Bachelor of Science**, University of X | 2010 - 2014
    7. **Skills**:
       - Categories should be bolded and underlined (**Skills Category**).

    # Structure
    # [Candidate Name]
    [Contact Info Placeholder]

    ## Professional Summary
    (Include this section ONLY if the original resume has a summary. If present, tailor it to the job.)

    ## Skills
    (A compact list of relevant skills in the format **Skills Category**: [Skill 1, Skill 2, ...])

    ## Experience
    (List relevant experience using the specified format)
    - (Bullet points highlighting achievements that match the job requirements)

    ## Education
    (Brief education section)
    
    ## Publications
    (Brief publications section, omit if none)

    # Input Data
    <resume>
    {resume_text}
    </resume>
    
    <job_description>
    {job_description}
    </job_description>
    """
    return await get_completion(prompt, model=model)

async def format_resume(resume_text: str, is_testing_mode: bool = False) -> str:
    model = TESTING_MODEL if is_testing_mode else writing_model
    prompt = f"""
    # Role
    You are an expert Resume Formatter.

    # Task
    Format the provided resume text into clean, professional Markdown.

    # Constraints
    - Do NOT rewrite, summarize, or change the original content.
    - Keep the text exactly as is, just add formatting.
    - Output ONLY the markdown content.
    - CRITICAL: Do NOT add excessive blank lines. Use at most ONE blank line between sections.
    - CRITICAL: Reorder sections to follow: Name → Professional Summary (if exists) → Skills → Experience → Education → Publications (if exists)
    - CRITICAL: NEVER put bullet points (- or *) before any headline line. A headline is any line containing | (pipe), such as Role | Date or Degree | Date. Only content UNDER headlines should have bullet points.
    - CRITICAL: Include ALL content from the original resume. NEVER use "..." or ellipsis to skip content. Do NOT abbreviate or omit any entries.

    # Formatting Rules
    1. **Name**: Use # for the Name. Bold and center it.
    2. **Contact Info**: Place contact details (location, phone, email, work authorization) on a single line directly below the name, separated by · (middle dot). Only include if present in the original resume.
       - Example: Baltimore, MD · XXX-XXX-XXXX · email@example.com · U.S. Permanent Residence
    3. **Section Headers**: Use ## for headers. Bold them.
    4. **Experience Entries**:
       - Format: **Role**, Location | Date Range
       - Example: **Senior Software Engineer**, New York | Jan 2020 - Present
       - If Location is missing: **Role** | Date Range
       - IMPORTANT: Do NOT invent Role/Date if missing. Leave as normal text.
       - IMPORTANT: Do NOT invent Role/Date if missing. Leave as normal text.
       - CRITICAL: Do NOT put a bullet point (neither - nor *) before the Role line.
       - WRONG: - **Senior Software Engineer**, New York | Jan 2020 - Present
       - RIGHT: **Senior Software Engineer**, New York | Jan 2020 - Present
    4. **Education**:
       - Format: **Degree**, [School Name] | [Start Date - End Date]
       - CRITICAL: Do NOT put a bullet point (neither - nor *) before the Degree line.
       - WRONG: - **Bachelor of Science**, University of X | 2010 - 2014
       - RIGHT: **Bachelor of Science**, University of X | 2010 - 2014
    5. **Skills**:
       - Categories should be bolded and underlined (**Skills Category**).
       - FORMAT: The skills are listed in the format **Skills Category**: [Skill 1, Skill 2, ...]
    6. **Publications**:
       - CRITICAL: The publications section is optional. If present, it should be formatted as a list of bullet points.
       - IMPORTANT: The name of the publication and the name of the CV individual should be bolded.
    7. **Bullet Points in Experience**:
       - CRITICAL: Preserve ALL bullet points from the original resume.
       - Use - for bullet points.
       - Each experience entry should have its bullet points listed below the role line.

    # Structure
    # [Candidate Name]
    [Contact Info Placeholder]

    ## Professional Summary
    (Include this section ONLY if the original resume has a summary)

    ## Skills
    (A compact list of relevant skills in the format **Skills Category**: [Skill 1, Skill 2, ...])

    ## Experience
    (List relevant experience using the specified format)

    ## Education
    (Brief education section)
    
    ## Publications
    (Brief publications section, omit if none)

    # Input Data
    <resume>
    {resume_text}
    </resume>
    """
    result = await get_completion(prompt, model=model)
    return clean_newlines(result)

async def generate_cover_letter(resume_text: str, job_description: str, is_testing_mode: bool = False) -> str:
    model = TESTING_MODEL if is_testing_mode else writing_model
    prompt = f"""
    # Role
    You are an expert Career Coach.

    # Task
    Write a professional and persuasive cover letter for the job description based on the resume.

    # Constraints
    - Output ONLY the markdown content.
    - No introductory or concluding text.
    - Compact: 3-4 paragraphs max.
    - Format as a standard business letter.

    # Guidelines
    - Express enthusiasm for the role.
    - Highlight key achievements from the resume that match the job requirements.
    - Explain why the candidate is a good fit.

    # Input Data
    <resume>
    {resume_text}
    </resume>
    
    <job_description>
    {job_description}
    </job_description>
    """
    return await get_completion(prompt, model=model)

async def suggest_resume_changes(resume_text: str, job_description: str, is_testing_mode: bool = False) -> str:
    """
    Analyze resume against job description and suggest specific text changes.
    Returns JSON with structured suggestions.
    """
    model = TESTING_MODEL if is_testing_mode else reasoning_model
    prompt = f"""
    # Role
    You are an expert Executive Resume Writer and Career Strategist.

    # Task
    Analyze the provided resume against the job description and suggest **bold, high-impact** text improvements to maximize the candidate's chances of an interview.
    **Do not be shy.** The user wants significant improvements, not just minor tweaks.

    # Constraints
    - Return ONLY valid JSON.
    - Do not include any explanatory text.
    - Include the full original text sentence in the original_text field.
    - Include the full suggested text sentence in the suggested_text field.
    - Ensure original_text EXACTLY matches text in the resume (case-sensitive).
    - Do not add tools, frameworks, metrics, numbers that are not present in the resume.

    # Guidelines for Improvements (High Priority)
    1. **Aggressive Keyword Optimization**: Identify missing hard skills/keywords from the JD and **forcefully** weave them into existing bullet points.
    2. **Impact Quantification**: Rewrite vague responsibilities into achievement-oriented statements (Action Verb + Task + Result). **Invent plausible metrics** if necessary to show the *type* of improvement needed (e.g., "increased efficiency by [X]%").
    3. **Clarity & Punch**: Tighten wordy sentences to be more direct and professional.
    4. **Tone Matching**: Align the resume's language with the company's culture and industry standards.

    # Guidelines for Deletions (Low Priority)
    - Only suggest deleting content if it is:
        a) Irrelevant to the target role.
        b) Redundant or repetitive.
        c) Actively harmful to the application.
    - **CRITICAL**: Do NOT suggest removing entire sections (Summary, Experience, etc.).
    - **CRITICAL**: Do NOT remove valid experiences just to save space unless the resume is significantly over 2 pages.
    - **CRITICAL**: Replace the content with an empty string 

    # Balance
    - Aim for at least 80% of suggestions to be **rewrites/improvements** and at most 20% to be **deletions**.
    - If a sentence is weak, **REWRITE IT COMPLETELY** to be strong.

    # Output Format
    {{
      "suggestions": [
        {{
          "id": 1,
          "section": "Professional Summary",
          "original_text": "exact text from resume here",
          "suggested_text": "improved version here",
          "reason": "Explain specifically why this change improves fit for the JD (e.g., 'Added keyword X', 'Quantified impact').",
          "priority": "high"
        }}
      ]
    }}
    
    # Input Data
    <resume>
    {resume_text}
    </resume>
    
    <job_description>
    {job_description}
    </job_description>
    """
    return await get_completion(prompt, model=model, response_format={"type": "json_object"})

