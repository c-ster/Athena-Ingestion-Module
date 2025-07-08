# Athena Multilingual Research Ingestion Module

A powerful tool for ingesting, processing, and analyzing academic research papers in multiple languages. This module provides a seamless pipeline for document upload, language translation, metadata extraction, and content analysis.

## 🌟 Features

- **Multilingual Support**: Automatically detects and translates documents
- **Document Processing**: Handles PDF, DOCX, and other common academic formats
- **Metadata Extraction**: Automatically extracts key information from documents
- **Real-time Updates**: Live status updates during file processing
- **Secure File Handling**: Built-in virus scanning and secure file storage

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Node.js 14+ (for frontend development)
- ClamAV (for virus scanning)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/c-ster/Athena-Ingestion-Module.git
   cd Athena-Ingestion-Module
   ```

2. Set up the backend:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and settings
   ```

4. Start the backend server:
   ```bash
   uvicorn main:app --reload
   ```

5. Open the frontend in your browser:
   ```
   open frontend/index.html
   ```

## 🏗️ System Architecture

### Frontend
- **Framework**: Static HTML, CSS, and JavaScript
- **Features**:
  - Drag-and-drop file upload
  - Real-time processing status
  - Document preview and management
  - Responsive design

### Backend
- **Framework**: Python (FastAPI)
- **Components**:
  - **REST API**: JSON endpoints for frontend communication
  - **Document Processing**:
    - File type detection and validation
    - Text extraction from various formats
    - Language detection and translation
    - Metadata extraction
  - **Security**:
    - File virus scanning (ClamAV)
    - Secure file handling
    - Input validation
        -   Document parsing.
        -   Metadata extraction.

### Storage
-   **Metadata**: Stored in a SQLite database.
-   **Uploaded Files**: Original files will be stored in a secure location on the server (`backend/uploads`).

### Security
-   **File Scanning**: Integration with a malware scanner (e.g., ClamAV) to scan all uploaded files.
-   **Sandboxing**: Processing of files will occur in an isolated environment to prevent potential security threats.
-   **Access Control**: Role-Based Access Control (RBAC) will be implemented to secure API endpoints.
-   **Data Encryption**: Data will be encrypted both in transit (using HTTPS) and at rest.

## Supported File Formats and Languages

### File Formats
The ingestion module supports the following file formats for academic research papers:
- PDF (.pdf)
- Microsoft Word (.docx)
- Plain Text (.txt)
- LaTeX (.tex)
- HTML (.html)
- XML (.xml)

### Translation Service

**Selected Service:** Microsoft Translator

Based on a review of services with DoD compliance, Microsoft Translator has been selected. It has received a FedRAMP public cloud attestation and is part of the Microsoft Azure ecosystem, which offers robust security and compliance features suitable for government-related projects.

### Document Parsing and NLP Libraries

To handle file parsing and Natural Language Processing (NLP), the following Python libraries have been selected:

-   **PDF Parsing**: `PyMuPDF` (fitz)
-   **DOCX Parsing**: `python-docx`
-   **HTML/XML Parsing**: `BeautifulSoup4`
-   **LaTeX Parsing**: A regular expression-based approach for common fields.
-   **Language Detection**: `langdetect`
-   **NLP for Metadata Extraction**: `spaCy`

### Metadata Schema

The following JSON schema will be used to store the extracted metadata for each ingested document:

```json
{
  "title": "string",
  "authors": [
    "string"
  ],
  "abstract": "string",
  "publication_date": "string (YYYY-MM-DD)",
  "keywords": [
    "string"
  ],
  "source_language": "string (e.g., 'en', 'fr')",
  "original_filename": "string",
  "ingestion_date": "string (ISO 8601 format)",
  "document_hash": "string (SHA-256)",
  "status": "string (e.g., 'uploaded', 'processing', 'completed', 'error')"
}
```

### UI/UX Wireframes (Textual)

This section outlines the initial wireframes for the file upload and review process.

**1. Upload Dashboard**
-   **Layout**: A central card with a clear call-to-action for file uploads.
-   **Components**:
    -   A drag-and-drop area.
    -   A file selector button.
    -   A list of files queued for upload, each with a progress bar and status indicator (e.g., 'Uploading', 'Processing', 'Complete').

**2. Metadata Review & Correction Page**
-   **Layout**: A form-based view for reviewing and editing extracted metadata.
-   **Components**:
    -   Editable fields for all metadata items (Title, Authors, Abstract, etc.).
    -   A 'Save' button to submit the corrected metadata.
    -   A 'Cancel' button to discard changes.
    -   A preview pane showing the translated abstract for easy reference.

### Cybersecurity Requirements

The following security measures will be implemented to protect the system:

-   **Malware Scanning**: All uploaded files will be scanned using an antivirus engine (e.g., ClamAV). Infected files will be rejected.
-   **Sandboxing**: File processing will be executed in an isolated, sandboxed environment (e.g., a Docker container) to contain any potential threats.
-   **Role-Based Access Control (RBAC)**: The system will enforce RBAC to ensure users can only access features and data appropriate for their role (e.g., Uploader, Reviewer, Admin).

### Languages
The system is designed to be language-agnostic. It will automatically detect the language of the uploaded document. If the document is not in English, it will be translated using a designated translation service before processing. This ensures that all documents are processed uniformly.
