import os
import re
from openai import AsyncOpenAI
from langfuse.openai import openai as langfuse_openai
import asyncio
from ddgs import DDGS
from dotenv import load_dotenv

load_dotenv()

# Initialize Langfuse - it reads LANGFUSE_SECRET_KEY, LANGFUSE_PUBLIC_KEY, 
# and LANGFUSE_BASE_URL from environment variables automatically
api_key = os.getenv("OPENAI_API_KEY")

# Use Langfuse-wrapped AsyncOpenAI client for automatic tracing
client = langfuse_openai.AsyncOpenAI(api_key=api_key) if api_key else None
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
    Please provide a structured, executive summary of the following job description. 
    The goal is to give the candidate the most critical information "at a glance".
    
    Structure the output in Markdown as follows:

    ## The Role
    (1-2 concise sentences describing the core essence of the role)

    ## Key Responsibilities
    - (3-5 bullet points of the most important day-to-day duties)

    ## Top Must-Haves
    - (3-5 bullet points of the non-negotiable hard skills or experiences)

    ## Why This Role?
    (1-2 sentences highlighting the benefits, culture, or unique selling points)
    
    ## Key Details
    - **Location**: (Extract or "Not specified")
    - **Salary**: (Extract if explicitly stated. IF NOT STATED: Estimate a realistic range based on the role title, location, and industry standards, and clearly label it as "$X - $Y (Estimated)". Do not leave this as "Not specified" unless it is impossible to estimate.)
    - **Work Type**: (Remote/Hybrid/Onsite/Contract/Full-time)

    Job Description:
    {job_description}
    """
    return await get_completion(prompt, model=model)

async def research_company(job_description: str, is_testing_mode: bool = False) -> str:
    """
    Research the company and role based on the job description.
    Returns JSON with structure:
    {
        "company_name": "...",
        "role_title": "...",
        "company_summary_markdown": "..."
    }
    """
    model = TESTING_MODEL if is_testing_mode else writing_model
    prompt = f"""
    Based on the following job description, perform deep research on the company and the role.
    
    # Task
    1. Identify the Company Name and Role Title.
    2. Identify the **Standardized Job Type** (e.g., Data Engineer, Software Engineer, Product Manager, Sales Representative). This should be a broad category.
    3. Write a comprehensive markdown summary of the company.
    
    # Output Format
    Return a valid JSON object with the following fields:
    - "company_name": The name of the hiring company. If not mentioned, use "Unknown Company".
    - "role_title": The title of the position.
    - "job_type": The standardized job category (e.g., "Data Scientist", "Backend Engineer", "Sales Rep").
    - "company_summary_markdown": A markdown-formatted summary with the following sections:
        ## Company Mission
        (A brief overview of the company's mission and what they do)

        ## Industry & Products
        (Details about the industry they operate in and their key products/services)

        ## Culture & Values
        (Any information about the company culture or values mentioned)

    # Job Description
    {job_description}
    """
    return await get_completion(prompt, model=model, response_format={"type": "json_object"})

async def extract_candidate_info(resume_text: str, is_testing_mode: bool = False) -> str:
    """
    Extract candidate metadata from the resume.
    Returns JSON with structure:
    {
        "name": "...",
        "email": "...",
        "phone": "..."
    }
    """
    model = TESTING_MODEL if is_testing_mode else writing_model
    prompt = f"""
    Extract the following metadata from the resume text.
    
    # Output Format
    Return a valid JSON object with the following fields:
    - "name": The candidate's full name.
    - "email": The candidate's email address (or null if not found).
    - "phone": The candidate's phone number (or null if not found).
    
    # Resume Text
    {resume_text}
    """
    return await get_completion(prompt, model=model, response_format={"type": "json_object"})

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
    - No introductory or concluding text (other than the letter itself).
    - Compact: 3-4 paragraphs max.
    - Format as a standard business letter.

    # Guidelines
    - Start with a header containing the candidate's name and contact details.
    - Format the Name as `# [Candidate Name]` (Centered by logic).
    - Format the contact details on the next line, separated by · (middle dot).
    - Example Header:
      # John Doe
      New York, NY · 555-555-5555 · email@example.com
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
    - Do NOT use "<" or ">" symbols in the output content. Use "less than" or "more than" instead to avoid parsing issues.

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

    return await get_completion(prompt, model=model, response_format={"type": "json_object"})


async def generate_outreach(resume_text: str, job_description: str, outreach_type: str, is_testing_mode: bool = False, company_name: str = "the company", role_title: str = "the role") -> str:
    model = TESTING_MODEL if is_testing_mode else writing_model
    
    type_prompts = {
        "linkedin_connection": f"""
            Write a short, engaging LinkedIn connection request message (max 300 characters).
            - The sender is a job candidate who has applied or wants to apply for the "{role_title}" role at "{company_name}".
            - The recipient is a recruiter, hiring manager, or employee at "{company_name}".
            - Express genuine interest in the role and the company.
            - Briefly mention why the candidate's background is a good fit for the role (not the recipient's expertise).
            - Be polite, professional, and not salesy.
            - Do NOT include "[Name]" placeholder - just start with "Hi," or similar.
        """,
        "hiring_manager_email": f"""
            Write a professional email to the Hiring Manager or Recruiter at {company_name}.
            - Subject Line: [Clear and catchy subject mentioning {role_title}]
            - Body: Pitch the candidate's core value proposition based on the resume and job description.
            - Keep it concise (under 200 words).
            - Call to Action: Request a brief chat.
        """,
        "follow_up_email": f"""
            Write a polite follow-up email to be sent 1 week after applying.
            - Reiterate interest in the {role_title} role at {company_name}.
            - Mention a specific reason why the candidate is a great fit (referencing a key skill).
            - Keep it very short.
        """
    }


    selected_prompt = type_prompts.get(outreach_type)
    if not selected_prompt:
        return "Error: Invalid outreach type selected."

    prompt = f"""
    # Role
    You are an expert Career Coach and Networking Strategist.

    # Task
    {selected_prompt}

    # Constraints
    - Output ONLY the message content.
    - No headers or markdown unless necessary for the email format (e.g. Subject:).
    - Use company culture and industry standards to align the message tone.
    - IMPORTANT: Use the actual company name "{company_name}" and role "{role_title}" directly. Do NOT use placeholders like [Company Name].
    
    # Context
    <resume_summary>
    {resume_text[:2000]}... (truncated for brevity)
    </resume_summary>
    
    <job_description>
    {job_description}
    </job_description>
    """
    return await get_completion(prompt, model=model)


async def bold_keywords(resume_text: str, job_description: str, job_type: str = "General Role", is_testing_mode: bool = False) -> str:
    model = TESTING_MODEL if is_testing_mode else writing_model
    prompt = f"""
    # Role
    You are an Expert Technical Recruiter specializing in hiring **{job_type}** professionals. Your goal is to highlight *competence* and *action*.

    # Task
    Analyze the provided Resume and Job Description (JD). Apply markdown bolding (**keyword**) to the Resume text.
    **CRITICAL GOAL**: Make the candidate's **Actions** and **Competencies** pop out. The recruiter wants to instantly see what the candidate DID (e.g., Led, Built, Creating).

    # Constraints
    1. **Preserve Content:** DO NOT change the text content. No grammar fixes or rewrites.
    2. **Avoid Over-bolding:** Limit bolding to high-impact keywords (15-25% of a bullet).
    3. **Existing Formatting:** Do not re-bold headers or existing bold text.
    4. **Structure:** Keep the same bullet points and line structure.

    # Bolding Strategy for a {job_type} (Prioritize in this order)
    1. **Action-Driven Competencies (Top Priority):** Bold phrases where a strong verb demonstrates a key capability (e.g., "**Led a team**", "**Architected a solution**", "**Created a dashboard**"). The VERB is the hero here.
    2. **Contextual Technologies:** Bold the technology *with* the action or context (e.g., "**Built** using **Python**", "**Deployed** on **AWS**").
    3. **Core Requirements:** Bold specific "Must Haves" from the JD.
    4. **Metrics (Lowest Priority):** Do NOT bold standalone numbers (e.g., "15%"). Only bold the impact description *around* the number (e.g., "**Reduced latency** by 40%").

    # What NOT to Bold
    - Do NOT bold generic buzzwords (e.g., "communication") unless it's a primary requirement.
    - Do NOT bold entire sentences.
    - Do NOT bold random numbers.

    # Example Transformation
    - JD Requirement (Data Engineer): "Experience with Java, Spring Boot, and Big Data pipelines."
    - Original: Developed a microservices architecture using Java and Spring Boot that reduced latency by 40%.
    - Improved: **Developed a microservices architecture** using **Java** and **Spring Boot** that **reduced latency** by 40%.
    - Original: Led a team of 5 engineers to build a dashboard.
    - Improved: **Led a team** of 5 engineers to **build a dashboard**.

    # Input Data
    <resume_text>
    {resume_text}
    </resume_text>
    
    <job_description>
    {job_description}
    </job_description>

    # Output Instruction
    Return ONLY the modified Resume markdown. Do not include any introductory or concluding remarks.
    """
    return await get_completion(prompt, model=model)


async def suggest_bold_changes(resume_text: str, job_description: str, job_type: str = "General Role", is_testing_mode: bool = False) -> list:
    """
    Generate bolding suggestions by comparing original resume with AI-bolded version.
    Returns a list of ResumeSuggestion objects.
    """
    import difflib

    # 1. Get the bolded version of the resume
    bolded_resume = await bold_keywords(resume_text, job_description, job_type, is_testing_mode)
    
    # 2. Robust Alignment using Difflib
    # We want to match original lines to bolded lines even if some lines are added/removed/changed.
    
    original_lines = resume_text.split('\n')
    bolded_lines = bolded_resume.split('\n')
    
    # We strip lines for comparison to handle whitespace differences, 
    # but we keep original indices to map back to the UI.
    
    # helper to clean for diffing (ignore bold markers AND whitespace)
    def clean_for_diff(text):
        return text.replace('**', '').strip()

    # Create sequence of "content" to match against
    # We'll use the indices to map back.
    matcher = difflib.SequenceMatcher(
        None, 
        [line.strip() for line in original_lines], 
        [clean_for_diff(line) for line in bolded_lines]
    )
    
    suggestions = []
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            # Lines [i1:i2] in original match [j1:j2] in bolded (content-wise)
            for k in range(i2 - i1):
                orig_idx = i1 + k
                bold_idx = j1 + k
                
                orig_text = original_lines[orig_idx]
                bold_text = bolded_lines[bold_idx]
                
                # Check if this matching line actually has bolding
                if '**' in bold_text and orig_text != bold_text:
                    # Double check content equality to be safe (matcher is pretty good though)
                    if clean_for_diff(bold_text) == orig_text.strip():
                        suggestions.append({
                            "id": 0,
                            "section": "Keyword Optimization",
                            "original_text": orig_text,
                            "suggested_text": bold_text,
                            "reason": "Highlighting key skills and metrics matching the job description.",
                            "priority": "medium"
                        })
        elif tag == 'replace':
            # The AI might have slightly changed the text (beyond just bolding).
            # If it's a small change + bolding, we might want to suggest it, but riskier.
            # For now, stick to 'equal' content to avoid hallucinations.
            pass
            
    if not suggestions:
        print(f"Debug: No bolding suggestions found. Stats: OrigLines={len(original_lines)}, BoldLines={len(bolded_lines)}")

    return suggestions


async def find_recruiters(company_name: str, job_description: str = "", limit: int = 5, is_testing_mode: bool = False) -> str:
    """
    Find recruiters using DuckDuckGo Search (external) and Job Description (internal).
    Returns a JSON string list of recruiter objects.
    """
    import json
    recruiters = []
    
    # 1. Internal Search: Extract from Job Description
    if job_description:
        try:
            model = TESTING_MODEL if is_testing_mode else writing_model
            internal_prompt = f"""
            # Task
            Extract specific recruiters, hiring managers, or talent acquisition contacts EXPLICITLY mentioned in the job description text below.
            
            # Constraints
            - Return ONLY a valid JSON object.
            - If no one is mentioned, return an empty array for "recruiters".
            - Do not Hallucinate or guess. Only extract names if they are present.
            
            # Output Format
            {{
                "recruiters": [
                    {{
                        "name": "Jane Doe",
                        "title": "Recruiter",
                        "url": "https://www.linkedin.com/in/janedoe (or null if no URL is mentioned)"
                    }}
                ]
            }}
            
            # Job Description
            {job_description[:10000]}
            """
            
            internal_res = await get_completion(internal_prompt, model=model, response_format={"type": "json_object"})
            # Cleanup potential markdown backticks just in case
            internal_res = internal_res.replace("```json", "").replace("```", "").strip()
            internal_data = json.loads(internal_res)
            
            for r in internal_data.get("recruiters", []):
                if r.get("name") and r.get("name") not in ["Unknown", "Hiring Manager"]:
                    recruiters.append(r)
        except Exception as e:
            print(f"Error extracting internal recruiters: {e}")

    # 2. External Search: DuckDuckGo
    if company_name and company_name != "Unknown Company":
        try:
            # Include "current" to prioritize active employees and filter out former employees
            query = f'site:linkedin.com/in/ "{company_name}" ("recruiter" OR "talent acquisition" OR "hiring manager") -"former" -"ex-" -"previously"'
            
            results = []
            try:
                loop = asyncio.get_running_loop()
                with DDGS() as ddgs:
                    results = await loop.run_in_executor(
                        None, lambda: ddgs.text(query, max_results=limit * 2)  # Fetch more to account for filtering
                    )
            except Exception as e:
                print(f"Error searching for recruiters: {e}")
                results = []

            if results:
                model = TESTING_MODEL if is_testing_mode else writing_model
                snippets_text = "\n\n".join([f"Result {i+1}:\nTitle: {r.get('title', '')}\nURL: {r.get('href', '')}\nSnippet: {r.get('body', '')}" for i, r in enumerate(results)])
                
                external_prompt = f"""
                # Task
                Extract a list of CURRENTLY ACTIVE recruiters at {company_name} from the search results below.
                Return valid JSON only.
                
                # CRITICAL CONSTRAINTS
                - ONLY include recruiters who are CURRENTLY working at {company_name}.
                - EXCLUDE anyone who:
                  - Has "Former", "Ex-", "Previously", "Past" in their title or description
                  - Lists {company_name} as a past employer
                  - Currently works at a DIFFERENT company
                - Look for indicators of current employment: "at {company_name}", "@ {company_name}", current job title without end date
                - If uncertain whether someone is currently employed, DO NOT include them.
                
                # Output Format
                {{
                    "recruiters": [
                        {{
                            "name": "Jane Doe",
                            "title": "Technical Recruiter at {company_name}",
                            "url": "https://www.linkedin.com/in/janedoe"
                        }}
                    ]
                }}
                
                # Search Results
                {snippets_text}
                """
                
                external_res = await get_completion(external_prompt, model=model, response_format={"type": "json_object"})
                external_data = json.loads(external_res)
                for r in external_data.get("recruiters", []):
                    # Simple deduplication by name
                    if not any(ex['name'].lower() == r['name'].lower() for ex in recruiters):
                         recruiters.append(r)
                         
        except Exception as e:
            print(f"Error in external recruiter search: {e}")

    # Return final list as JSON string
    return json.dumps(recruiters)