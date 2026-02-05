# Eleviro

**Eleviro** is an AI-powered job application assistant designed to streamline the process of refining your resume and creating tailored cover letters. By analyzing both your resume and the specific job description, Eleviro helps you put your best foot forward.

## 🚀 Key Features

*   **Intelligent Job Analysis**: Scrapes job descriptions directly from URLs or accepts raw text to identify key skills and requirements.
*   **Resume Parsing**: Supports uploading existing resumes in both **PDF** and **DOCX** formats. The parser uses regex-based section detection (Summary, Experience, Education, Skills, etc.) and optional AI to refine sections and subsections. **OCR** (Tesseract) is used automatically when PDF text extraction is poor (e.g. scanned PDFs or text in images, such as a candidate name in a header). See `docs/PARSER_REQUIREMENTS.md` and `docs/PARSER_DESIGN.md` for details.
*   **AI-Powered Tailoring**: Uses advanced AI models (via OpenAI) to suggest specific optimizations for your Professional Summary and Experience bullet points, ensuring they align with the job description.
*   **Automated Cover Letters**: Generates personalized, professional cover letters based on your experience and the job's context.
*   **Professional Export**: Downloads your adapted resume as a cleanly formatted DOCX file, featuring:
    *   **Calibri** font for a modern, professional look.
    *   **Centered Header** for your name and contact details.
    *   Optimized formatting for readability.
*   **Recruiter & Hiring Manager Discovery**: Automatically identifies key decision-makers and their contact details (LinkedIn profiles) to facilitate direct networking.
*   **Cold Outreach Generator**: Creates personalized cold outreach messages tailored to specific recruiters or hiring managers.
*   **Smart Formatting**: Optional "Bold Keywords" feature to highlight relevant skills and impact in your resume.
*   **Editable AI Suggestions**: Review and refine AI-generated content for your resume and cover letter before finalizing.
*   **Testing Mode**: Includes a built-in testing mode for faster, cost-effective experimentation.

## 🛠️ Tech Stack

*   **Frontend**: HTML, CSS, JavaScript (Vanilla)
*   **Backend**: Python, FastAPI
*   **AI Engine**: OpenAI API
*   **Observability**: Langfuse
*   **Search**: DuckDuckGo Search
*   **Document Processing**: `python-docx`, `pypdf`, `BeautifulSoup4`; optional OCR: `pymupdf`, `pytesseract`, `Pillow`

## 🏁 Getting Started

### Prerequisites

*   Python 3.8+
*   An OpenAI API Key
*   **Optional (for OCR on scanned/image PDFs):** [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) installed and on your PATH (e.g. `brew install tesseract` on macOS, `apt-get install tesseract-ocr` on Debian/Ubuntu). If Tesseract is not installed, PDF parsing still works for normal text-based PDFs.

### Installation

1.  **Clone the repository**:
    ```bash
    git clone <repository-url>
    cd eleviro
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure Environment**:
    Create a `.env` file in the root directory and add your OpenAI API key and Langfuse credentials:
    ```env
    OPENAI_API_KEY=your_api_key_here
    LANGFUSE_PUBLIC_KEY=your_public_key
    LANGFUSE_SECRET_KEY=your_secret_key
    LANGFUSE_HOST=your_langfuse_host
    ```

### Running the Application

Start the local development server:

```bash
uvicorn main:app --reload
```

Open your browser and navigate to `http://localhost:8000` to start using Eleviro.
