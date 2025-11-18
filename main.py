import os
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional
from datetime import datetime
import uuid

from database import db, create_document, get_documents
from schemas import Subject, Book, LessonRequest, Lesson, Schedule, Progress

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "AI Tutor Backend is running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Connected & Working"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name
            response["connection_status"] = "Connected"
            response["collections"] = db.list_collection_names()[:10]
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:100]}"
    return response


# Simple dependency to simulate authenticated user id
# In production you'll verify Supabase JWT and extract user id

def get_current_user_id(x_user_id: Optional[str] = None):
    # This is a placeholder for real auth integration.
    # Expecting frontend to send X-User-Id header from Supabase session.user.id
    return x_user_id


# Subjects
@app.post("/api/subjects")
def create_subject(subject: Subject, user_id: Optional[str] = Depends(get_current_user_id)):
    if not user_id:
        user_id = subject.user_id
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing user id")
    payload = subject.model_dump()
    payload["user_id"] = user_id
    _id = create_document("subject", payload)
    return {"id": _id}


@app.get("/api/subjects")
def list_subjects(user_id: Optional[str] = Depends(get_current_user_id)):
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing user id")
    items = get_documents("subject", {"user_id": user_id})
    return items


# Books and PDF upload
UPLOAD_DIR = os.path.join("uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.post("/api/books/upload")
async def upload_book(
    user_id: str = Form(...),
    subject_id: str = Form(...),
    file: UploadFile = File(...),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    book_id = str(uuid.uuid4())
    fname = f"{book_id}-{file.filename}"
    fpath = os.path.join(UPLOAD_DIR, fname)

    with open(fpath, "wb") as out:
        out.write(await file.read())

    # Naive text extraction placeholder (no heavy libs). In production, use n8n to extract.
    # We'll just store metadata; extracted pages can be added later by n8n callback.
    book = Book(
        user_id=user_id,
        subject_id=subject_id,
        title=file.filename.replace(".pdf", ""),
        original_filename=file.filename,
        file_path=fpath,
        pages=None,
        num_pages=None,
    )
    _id = create_document("book", book)
    return {"id": _id, "file_path": fpath}


@app.get("/api/books")
def list_books(subject_id: str, user_id: Optional[str] = Depends(get_current_user_id)):
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing user id")
    items = get_documents("book", {"user_id": user_id, "subject_id": subject_id})
    return items


# Lessons and progress tracking
@app.post("/api/lessons")
def request_lesson(req: LessonRequest, user_id: Optional[str] = Depends(get_current_user_id)):
    if not user_id:
        user_id = req.user_id
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing user id")

    lesson = Lesson(
        user_id=user_id,
        subject_id=req.subject_id,
        book_id=req.book_id,
        prompt=req.prompt,
        status="pending",
    )
    _id = create_document("lesson", lesson)

    # Here you would trigger n8n workflow with the lesson id
    # n8n will: extract the exact excerpt from the PDF, call LLM to explain with analogies,
    # and PATCH back to /api/lessons/{id} with results. For now, we keep it pending.

    return {"id": _id, "status": "queued"}


@app.get("/api/progress")
def get_progress(book_id: str, user_id: Optional[str] = Depends(get_current_user_id)):
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing user id")
    items = get_documents("progress", {"user_id": user_id, "book_id": book_id})
    return items


@app.post("/api/progress")
def upsert_progress(progress: Progress, user_id: Optional[str] = Depends(get_current_user_id)):
    if not user_id:
        user_id = progress.user_id
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing user id")

    # Simple upsert by user+book
    existing = db["progress"].find_one({"user_id": user_id, "book_id": progress.book_id})
    payload = progress.model_dump()
    payload["user_id"] = user_id
    if existing:
        db["progress"].update_one({"_id": existing["_id"]}, {"$set": {**payload, "updated_at": datetime.utcnow()}})
        return {"id": str(existing["_id"]) }
    else:
        _id = create_document("progress", payload)
        return {"id": _id}


# Scheduling via n8n
@app.post("/api/schedules")
def create_schedule(s: Schedule, user_id: Optional[str] = Depends(get_current_user_id)):
    if not user_id:
        user_id = s.user_id
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing user id")

    payload = s.model_dump()
    payload["user_id"] = user_id

    # Call n8n webhook to register a schedule; store returned job id
    # Example placeholder: n8n_job_id = requests.post(N8N_URL, json=payload).json()["id"]
    payload["n8n_job_id"] = payload.get("n8n_job_id") or str(uuid.uuid4())

    _id = create_document("schedule", payload)
    return {"id": _id, "n8n_job_id": payload["n8n_job_id"]}


# Callback endpoints for n8n to update lesson results
@app.patch("/api/lessons/{lesson_id}")
def patch_lesson(lesson_id: str, status: Optional[str] = None, input_excerpt: Optional[str] = None,
                 explanation: Optional[str] = None, analogies: Optional[List[str]] = None, error: Optional[str] = None):
    doc = db["lesson"].find_one({"_id": {"$eq": db["lesson"].get_serializer().to_bson(lesson_id)}})
    # Fallback if serializer not present; try string id match
    if not doc:
        doc = db["lesson"].find_one({"_id": lesson_id})

    updates = {k: v for k, v in {
        "status": status,
        "input_excerpt": input_excerpt,
        "explanation": explanation,
        "analogies": analogies,
        "error": error,
        "updated_at": datetime.utcnow(),
    }.items() if v is not None}

    db["lesson"].update_one({"_id": doc["_id"]}, {"$set": updates})
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
