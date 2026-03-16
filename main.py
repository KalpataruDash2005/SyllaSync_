import asyncio
import uuid
import os
import shutil
import logging
from pathlib import Path
from typing import List, Dict
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

# --- Imports from your other files ---
from models import UploadResponse, ProgressEvent
from pdf_processor import PDFProcessor

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
jobs: Dict[str, dict] = {}

async def _process_logic(job_id: str, file_paths: List[str]):
    """The background processing pipeline."""
    try:
        jobs[job_id].update({"status": "processing", "progress": 15, "step": "Extracting text..."})
        processor = PDFProcessor()
        
        extracted_docs = []
        for fp in file_paths:
            doc = await processor.extract(fp)
            extracted_docs.append(doc)
        
        jobs[job_id].update({"progress": 40, "step": "Organizing content..."})
        organized = processor.organize(extracted_docs)
        
        jobs[job_id].update({"progress": 70, "step": "AI is generating your plan..."})
        await asyncio.sleep(2) 
        
        jobs[job_id].update({
            "status": "completed",
            "progress": 100,
            "step": "Study plan ready! 🎉",
            "result": {
                "course_name": organized.course_name_guess,
                "weeks": [], 
                "global_memory_techniques": {}
            }
        })
        
        # Cleanup uploaded files
        shutil.rmtree(Path(file_paths[0]).parent, ignore_errors=True)

    except Exception as e:
        logging.error(f"Error: {e}")
        jobs[job_id].update({"status": "failed", "error": str(e)})

@app.post("/api/upload", response_model=UploadResponse)
async def upload_files(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    job_id = str(uuid.uuid4())
    job_dir = UPLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    
    saved_paths = []
    for f in files:
        destination = job_dir / f.filename
        with destination.open("wb") as buffer:
            shutil.copyfileobj(f.file, buffer)
        saved_paths.append(str(destination))
    
    jobs[job_id] = {"status": "queued", "progress": 5, "step": "Queued..."}
    background_tasks.add_task(_process_logic, job_id, saved_paths)
    
    return UploadResponse(job_id=job_id, status="queued", file_count=len(files), message="Started")

@app.get("/api/progress/{job_id}")
async def stream_progress(job_id: str):
    async def event_generator():
        while True:
            job = jobs.get(job_id)
            if not job: break
            yield f"data: {ProgressEvent(**job).model_dump_json()}\n\n"
            if job["status"] in ["completed", "failed"]: break
            await asyncio.sleep(1)
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# Serve Frontend
frontend_path = Path(__file__).parent / "frontend"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="static")

# ─── THIS REPLACES THE UVICORN COMMAND ───
if __name__ == "__main__":
    import uvicorn
    # Change to 0.0.0.0
    uvicorn.run(app, host="0.0.0.0", port=8000)