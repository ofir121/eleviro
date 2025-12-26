import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None

def get_completion(prompt: str, model: str = "gpt-3.5-turbo"):
    if not client:
        return "Error: OPENAI_API_KEY not found. Please set it in the .env file."
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        return "Error generating content. Please check your API key and try again."

def summarize_job(job_description: str) -> str:
    prompt = f"""
    Please summarize the following job description. Format the output using Markdown.
    Output ONLY the markdown content. Do not include any introductory or concluding text.
    Structure the summary with the following sections:
    
    ## Role Overview
    (A brief paragraph describing the role)

    ## Key Responsibilities
    (A bulleted list of the main responsibilities)

    ## Required Skills & Qualifications
    (A bulleted list of the required skills and qualifications)
    
    Job Description:
    {job_description}
    """
    return get_completion(prompt)

def summarize_company(job_description: str) -> str:
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
    return get_completion(prompt)

def adapt_resume(resume_text: str, job_description: str) -> str:
    prompt = f"""
    I have a resume and a job description. Please adapt the resume to better match the job description. 
    Format the output as a professional CV using Markdown. 
    Output ONLY the markdown content. Do not include any introductory or concluding text.
    
    IMPORTANT: For the Experience section, format the role and date on the same line separated by a pipe character "|".
    Example: **Software Engineer at Google** | **Jan 2020 - Present**
    
    Use the following structure:

    # [Candidate Name]
    [Contact Info Placeholder]

    ## Professional Summary
    (A strong summary tailored to the job)

    ## Experience
    (List relevant experience. Remember to use the "Role | Date" format for headers)
    - (Bullet points highlighting achievements that match the job requirements)

    ## Education
    (Brief education section)

    ## Skills
    (A compact list of relevant skills)
    
    Resume:
    {resume_text}
    
    Job Description:
    {job_description}
    """
    return get_completion(prompt)

def generate_cover_letter(resume_text: str, job_description: str) -> str:
    prompt = f"""
    Write a professional and persuasive cover letter for the following job description, based on the provided resume.
    Output ONLY the markdown content. Do not include any introductory or concluding text.
    The cover letter should be compact, no more than 3-4 paragraphs.
    Express enthusiasm for the role, highlight key achievements from the resume that match the job requirements, and explain why I am a good fit.
    Format it as a standard business letter.
    
    Resume:
    {resume_text}
    
    Job Description:
    {job_description}
    """
    return get_completion(prompt)
