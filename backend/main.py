import os
import shutil
import subprocess
from typing import List

import asyncio
import json
from fastapi import FastAPI, BackgroundTasks, Depends, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse
from dotenv import load_dotenv
import logging

# Load environment variables from .env file
load_dotenv()

# Debug: Print environment variables
print("\n=== Environment Variables ===")
print(f"TRANSLATOR_API_KEY: {'Set' if os.getenv('TRANSLATOR_API_KEY') else 'Not Set'}")
print(f"TRANSLATOR_LOCATION: {os.getenv('TRANSLATOR_LOCATION')}")
print(f"OPENAI_API_KEY: {'Set' if os.getenv('OPENAI_API_KEY') else 'Not Set'}")
print(f"OPENAI_MODEL: {os.getenv('OPENAI_MODEL')}")
print("==========================\n")

from text_extraction import (
    extract_text_from_pdf,
    extract_text_from_docx,
    extract_text_from_txt,
    extract_text_from_html,
    extract_text_from_xml
)
from translation import translate_text
from metadata_extraction import process_file_metadata

app = FastAPI()

# Global queue to hold status messages for SSE
status_queue = asyncio.Queue()

async def status_event_generator(request: Request):
    """Yields status updates from the queue to the client."""
    while True:
        if await request.is_disconnected():
            print("Client disconnected, closing SSE stream.")
            break
        try:
            message = await asyncio.wait_for(status_queue.get(), timeout=1.0)
            yield json.dumps(message)
        except asyncio.TimeoutError:
            # Send a keep-alive comment if no message is available
            yield ": keep-alive\n\n"
        except Exception as e:
            print(f"Error in SSE generator: {e}")

@app.get("/api/status")
async def get_status_updates(request: Request):
    """Endpoint to stream status updates using Server-Sent Events."""
    return EventSourceResponse(status_event_generator(request))

UPLOADS_DIR = "uploads"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".tex", ".html", ".xml"}

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

@app.on_event("startup")
def startup_event():
    if not os.path.exists(UPLOADS_DIR):
        os.makedirs(UPLOADS_DIR)
    print("Uploads directory created.")

@app.on_event("shutdown")
def shutdown_event():
    print("Application shutting down.")

async def scan_file(file_path: str):
    """Scans a file for malware using ClamAV."""
    try:
        result = subprocess.run(
            ["clamscan", "--no-summary", file_path],
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode == 1:
            os.remove(file_path)
            raise HTTPException(
                status_code=400,
                detail=f"Malware detected in file: {os.path.basename(file_path)}. Upload rejected."
            )
        elif result.returncode != 0:
            print(f"ClamAV scan error for {file_path}: {result.stderr}")
            os.remove(file_path)
            raise HTTPException(
                status_code=500,
                detail="An error occurred during malware scanning. The file has been removed."
            )
    except FileNotFoundError:
        print("CRITICAL: `clamscan` executable not found. Malware scanning is disabled.")
        pass
    except Exception as e:
        print(f"An unexpected error occurred during malware scan: {e}")
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=500,
            detail="An unexpected server error occurred during file security processing."
        )


async def process_and_translate_file(file_path: str, file_ext: str, filename: str):
    """Extracts text, translates it, and saves the translation."""
    text_extractors = {
        ".pdf": extract_text_from_pdf,
        ".docx": extract_text_from_docx,
        ".txt": extract_text_from_txt,
        ".html": extract_text_from_html,
        ".xml": extract_text_from_xml,
        ".tex": extract_text_from_txt,  # Treat LaTeX as plain text for now
    }

    try:
        # 1. Extract Text
        extractor = text_extractors.get(file_ext)
        if not extractor:
            print(f"No text extractor found for {file_ext}. Skipping translation.")
            return

        await status_queue.put({"filename": filename, "status": "Processing..."})
        print(f"Extracting text from {os.path.basename(file_path)}...")
        original_text = await asyncio.to_thread(extractor, file_path)

        if not original_text.strip():
            print(f"No text found in {os.path.basename(file_path)}. Skipping translation.")
            return

        # 2. Translate Text First
        await status_queue.put({"filename": filename, "status": "Translating..."})
        print(f"Translating text for {os.path.basename(file_path)}...")
        translated_text = await translate_text(original_text)
        
        # 3. Process and save metadata using the translated text
        await process_and_save_metadata(file_path, file_ext, translated_text, filename)

        # 4. Save Translated File
        if translated_text:
            base_filename = os.path.splitext(os.path.basename(file_path))[0]
            translated_filename = f"{base_filename}_translated.txt"
            translated_file_path = os.path.join(UPLOADS_DIR, translated_filename)

            with open(translated_file_path, "w", encoding="utf-8") as f:
                f.write(translated_text)

            print(f"Translated text saved to {translated_filename}")

    except Exception as e:
        print(f"An error occurred during processing and translation of {os.path.basename(file_path)}: {e}")
        # We don't re-raise here to allow other files to be processed


async def process_and_save_metadata(file_path, file_ext, text_content, filename: str):
    """
    Processes and saves metadata for a file with enhanced error handling.
    
    Args:
        file_path: Path to the file
        file_ext: File extension
        text_content: Extracted text content
        filename: Original filename
        
    Returns:
        Dictionary containing the processed metadata
    """
    base_filename = os.path.splitext(os.path.basename(file_path))[0]
    metadata_filename = f"{base_filename}_metadata.json"
    metadata_path = os.path.join(UPLOADS_DIR, metadata_filename)
    
    # Default minimal metadata in case of errors
    minimal_metadata = {
        'title': base_filename,
        'authors': ['No Authors'],
        'abstract': 'No abstract available',
        'keywords': ['general']
    }
    
    try:
        # Update status
        await status_queue.put({"filename": filename, "status": "Extracting Metadata..."})
        
        # Process metadata asynchronously
        metadata = await process_file_metadata(file_path, file_ext, text_content)
        
        # Ensure we have at least the minimal required fields
        if not metadata:
            metadata = minimal_metadata
        
        # Save the metadata to a file
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=4, default=str)

        print(f"Metadata saved for {os.path.basename(file_path)}")
        return metadata
        
    except Exception as e:
        error_msg = f"Error processing metadata for {os.path.basename(file_path)}: {str(e)}"
        print(error_msg)
        
        # Save error information to the metadata
        minimal_metadata['error'] = error_msg
        
        try:
            # Still try to save the minimal metadata
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(minimal_metadata, f, ensure_ascii=False, indent=4, default=str)
        except Exception as save_error:
            print(f"Failed to save minimal metadata: {save_error}")
        
        return minimal_metadata


async def process_file_in_background(filename: str, file_ext: str, file_path: str):
    """Runs the full processing pipeline for a file in a background task."""
    try:
        await status_queue.put({"filename": filename, "status": "Scanning for malware..."})
        await scan_file(file_path)

        await process_and_translate_file(file_path, file_ext, filename)
        await status_queue.put({"filename": filename, "status": "Complete", "detail": "Processing finished successfully."})
        return {"filename": filename, "status": "success"}

    except HTTPException as http_exc:
        if os.path.exists(file_path):
            os.path.exists(file_path) and os.remove(file_path)
        error_msg = f"{http_exc.detail}"
        await status_queue.put({"filename": filename, "status": "Error", "detail": error_msg})
        return {"filename": filename, "status": "error", "error": error_msg}
        
    except Exception as e:
        if os.path.exists(file_path):
            os.path.exists(file_path) and os.remove(file_path)
        error_msg = f"An unexpected error occurred: {str(e)}"
        await status_queue.put({"filename": filename, "status": "Error", "detail": error_msg})
        return {"filename": filename, "status": "error", "error": error_msg}

async def process_single_file(file: UploadFile) -> dict:
    """Process a single uploaded file and return the result."""
    filename = file.filename
    file_ext = os.path.splitext(filename)[1].lower()
    file_path = os.path.join(UPLOADS_DIR, filename)
    
    try:
        # Check file extension
        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"File type not allowed for {filename}")
        
        # Save the file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size > MAX_FILE_SIZE:
            os.path.exists(file_path) and os.remove(file_path)
            raise HTTPException(status_code=413, detail=f"File size exceeds limit for {filename}")
        
        # Process the file in the background
        return await process_file_in_background(filename, file_ext, file_path)
        
    except Exception as e:
        if os.path.exists(file_path):
            os.path.exists(file_path) and os.remove(file_path)
        error_msg = str(e.detail) if hasattr(e, 'detail') else str(e)
        return {
            "filename": filename,
            "status": "error",
            "error": f"Failed to process file {filename}: {error_msg}"
        }

@app.post("/api/upload/")
async def upload_files(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    """
    Handles multiple file uploads, saves them, and schedules them for background processing.
    
    Args:
        files: List of uploaded files
        
    Returns:
        dict: Status message with details about the upload
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    # Process files in parallel
    tasks = [process_single_file(file) for file in files]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Count successful and failed uploads
    success_count = sum(1 for r in results if isinstance(r, dict) and r.get('status') == 'success')
    error_count = len(files) - success_count
    
    return {
        "message": f"Started processing {len(files)} file(s)",
        "successful": success_count,
        "failed": error_count,
        "details": results
    }


@app.get("/api/files/")
async def get_uploaded_files():
    """Returns a list of uploaded files with their translated and metadata counterparts.
    
    Returns:
        A dictionary with a 'files' key containing a list of file objects.
        Each file object contains:
        - filename: Original filename
        - translated_filename: Name of the translated file (if exists)
        - metadata: Dictionary of metadata (if exists)
    """
    try:
        files = os.listdir(UPLOADS_DIR)
        file_map = {}
        
        # First pass: build a map of all files by their base names
        for filename in files:
            if filename.startswith('.'):
                continue
                
            # Handle different file types
            if filename.endswith('_translated.txt'):
                base_name = filename[:-len('_translated.txt')]
                file_map.setdefault(base_name, {})['translated_filename'] = filename
            elif filename.endswith('_metadata.json'):
                base_name = filename[:-len('_metadata.json')]
                try:
                    with open(os.path.join(UPLOADS_DIR, filename), 'r', encoding='utf-8') as f:
                        file_map.setdefault(base_name, {})['metadata'] = json.load(f)
                except Exception as e:
                    print(f"Error reading metadata file {filename}: {e}")
            else:
                # This is an original file
                base_name = os.path.splitext(filename)[0]
                file_map.setdefault(base_name, {})['filename'] = filename
        
        # Convert the map to the expected format
        result = []
        for base_name, file_info in file_map.items():
            # Only include entries that have an original filename
            if 'filename' in file_info:
                result.append({
                    'filename': file_info['filename'],
                    'translated_filename': file_info.get('translated_filename'),
                    'metadata': file_info.get('metadata')
                })
        
        return {"files": result}
        
    except Exception as e:
        print(f"Error in get_uploaded_files: {e}")
        return {"files": [], "error": str(e)}


# Mount the uploads directory to make files accessible
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

# Mount the frontend directory to serve static files
# This must be done AFTER all API routes are defined
app.mount("/", StaticFiles(directory="../frontend", html=True), name="static")

