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

# Load environment variables from .env file
load_dotenv()

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

        # 2. Process and save metadata
        await process_and_save_metadata(file_path, file_ext, original_text, filename)

        # 3. Translate Text
        await status_queue.put({"filename": filename, "status": "Translating..."})
        print(f"Translating text for {os.path.basename(file_path)}...")
        translated_text = await translate_text(original_text)

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
    """Processes and saves metadata for a file."""
    try:
        await status_queue.put({"filename": filename, "status": "Extracting Metadata..."})
        metadata = await asyncio.to_thread(process_file_metadata, file_path, file_ext, text_content)
        base_filename = os.path.splitext(os.path.basename(file_path))[0]
        metadata_filename = f"{base_filename}_metadata.json"
        metadata_path = os.path.join(UPLOADS_DIR, metadata_filename)

        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=4)

        print(f"Metadata saved for {os.path.basename(file_path)}")
    except Exception as e:
        print(f"An error occurred during metadata processing for {os.path.basename(file_path)}: {e}")


async def process_file_in_background(filename: str, file_ext: str, file_path: str):
    """Runs the full processing pipeline for a file in a background task."""
    try:
        await status_queue.put({"filename": filename, "status": "Scanning for malware..."})
        await scan_file(file_path)

        await process_and_translate_file(file_path, file_ext, filename)
        await status_queue.put({"filename": filename, "status": "Complete", "detail": "Processing finished successfully."})

    except HTTPException as http_exc:
        if os.path.exists(file_path):
            os.remove(file_path)
        await status_queue.put({"filename": filename, "status": "Error", "detail": http_exc.detail})
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        await status_queue.put({"filename": filename, "status": "Error", "detail": f"An unexpected error occurred: {e}"})

@app.post("/api/upload/")
async def upload_files(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    """Handles file uploads, saves them, and schedules them for background processing."""
    for file in files:
        filename = file.filename
        file_ext = os.path.splitext(filename)[1].lower()
        file_path = os.path.join(UPLOADS_DIR, filename)

        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"File type not allowed for {filename}")

        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            file_size = os.path.getsize(file_path)
            if file_size > MAX_FILE_SIZE:
                os.remove(file_path)
                raise HTTPException(status_code=413, detail=f"File size exceeds limit for {filename}")
            
            background_tasks.add_task(process_file_in_background, filename, file_ext, file_path)

        except Exception as e:
            if os.path.exists(file_path):
                os.remove(file_path)
            raise HTTPException(status_code=500, detail=f"Failed to save file {filename}: {e}")

    return {"message": f"Started processing {len(files)} file(s) in the background."}


@app.get("/api/files/")
async def get_uploaded_files():
    """Returns a list of uploaded files with their translated and metadata counterparts."""
    files = os.listdir(UPLOADS_DIR)
    processed_files = {}

    # First pass: collect all original files
    for filename in files:
        if filename.startswith('.') or filename.endswith(('_translated.txt', '_metadata.json')):
            continue
        base_name = os.path.splitext(filename)[0]
        if base_name not in processed_files:
            processed_files[base_name] = {"filename": filename}

    # Second pass: attach translated files and metadata
    for filename in files:
        if filename.endswith('_translated.txt'):
            base_name = filename.replace('_translated.txt', '')
            if base_name in processed_files:
                processed_files[base_name]['translated_filename'] = filename
        elif filename.endswith('_metadata.json'):
            base_name = filename.replace('_metadata.json', '')
            if base_name in processed_files:
                try:
                    with open(os.path.join(UPLOADS_DIR, filename), 'r', encoding='utf-8') as f:
                        processed_files[base_name]['metadata'] = json.load(f)
                except Exception as e:
                    print(f"Error reading metadata file {filename}: {e}")

    return {"files": list(processed_files.values())}


# Mount the uploads directory to make files accessible
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

# Mount the frontend directory to serve static files
# This must be done AFTER all API routes are defined
app.mount("/", StaticFiles(directory="../frontend", html=True), name="static")

