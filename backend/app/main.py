import asyncio
import csv
import io
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from app.local_model import predict_image

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "plantcare.db")))
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads")))
API_KEY = os.getenv("PLANT_HEALTH_API_KEY", "").strip()
API_URL = os.getenv("PLANT_HEALTH_API_URL", "https://planthealthengine.com/api/v1/diagnose")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "8"))
ALLOWED_ORIGINS = [x.strip() for x in os.getenv("CORS_ORIGINS", "*").split(",") if x.strip()]

DB_PATH.parent.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="PlantCare AI Research API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS != ["*"] else ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS scans (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            crop TEXT NOT NULL,
            disease TEXT NOT NULL,
            confidence REAL,
            result_status TEXT,
            sample_code TEXT,
            observer TEXT,
            notes TEXT,
            image_filename TEXT NOT NULL,
            provider_response TEXT
        )
        """)
init_db()

def safe_float(value):
    try:
        if value is None: return None
        return float(value)
    except (TypeError, ValueError):
        return None

def extract_diagnosis(payload: dict):
    # Provider's documented response uses result, disease, confidence and treatment.
    result = payload.get("result", "unknown")
    disease = payload.get("disease") or payload.get("diagnosis") or payload.get("label")
    confidence = safe_float(payload.get("confidence"))
    treatment = payload.get("treatment") or {}
    if isinstance(treatment, str):
        treatment = {"cure": treatment}
    if not disease and isinstance(payload.get("predictions"), list) and payload["predictions"]:
        top = payload["predictions"][0]
        disease = top.get("disease") or top.get("label") or top.get("name")
        confidence = safe_float(top.get("confidence", confidence))
    return result, disease or "No disease label returned", confidence, treatment

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "PlantCare AI Research API",
        "provider_configured": bool(API_KEY),
        "database": "sqlite"
    }

@app.post("/api/diagnose")
async def diagnose(
    image: UploadFile = File(...),
    crop: str = Form(...),
    sample_code: str = Form(""),
    observer: str = Form(""),
    notes: str = Form("")
):
           
    crop = crop.strip().lower()

    if not crop or len(crop) > 60:
        raise HTTPException(status_code=400, detail="Please select a valid crop.")

    if image.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=415, detail="Upload a JPG, PNG, or WebP image.")

    raw = await image.read()

    if not raw:
        raise HTTPException(status_code=400, detail="The uploaded image is empty.")

    if len(raw) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"Image must be smaller than {MAX_UPLOAD_MB} MB."
        )

    suffix = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp"
    }[image.content_type]

    scan_id = str(uuid.uuid4())
    filename = f"{scan_id}{suffix}"
    image_path = UPLOAD_DIR / filename

    # Run the trained local AI model
    try:
        prediction = await asyncio.to_thread(predict_image, raw)

    except (OSError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="Could not read this image. Please upload a clear JPG, PNG, or WebP image."
        )

    predicted_crop = prediction["crop"].strip()

    # Verify that the selected crop matches the model prediction
    if predicted_crop.lower() != crop:
        raise HTTPException(
            status_code=400,
            detail=(
                f"The model identifies this image as {predicted_crop}, "
                f"but you selected {crop.title()}. "
                "Please check the crop selection or upload another image."
            )
        )

    # Prepare the local model result
    result_status = (
        "healthy"
        if "healthy" in prediction["class_name"].lower()
        else "disease_detected"
    )

    payload = {
        "result": result_status,
        "crop": predicted_crop,
        "disease": prediction["disease"],
        "confidence": prediction["confidence"],
        "treatment": {
            "cure": prediction["treatment"]
        },
        "severity": prediction["severity"],
        "pathogen": prediction["pathogen"],
        "model": "EfficientNet-B4 local model"
    }

 

    result_status, disease, confidence, treatment = extract_diagnosis(payload)
    image_path.write_bytes(raw)
    created_at = datetime.now(timezone.utc).isoformat()

    with db() as con:
        con.execute("""
            INSERT INTO scans
            (id, created_at, crop, disease, confidence, result_status, sample_code, observer, notes, image_filename, provider_response)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            scan_id, created_at, crop, disease, confidence, str(result_status),
            sample_code.strip(), observer.strip(), notes.strip(), filename,
            json.dumps(payload, ensure_ascii=False)
        ))

    return {
        "id": scan_id,
        "created_at": created_at,
        "crop": crop,
        "disease": disease,
        "confidence": confidence,
        "result_status": result_status,
        "treatment": treatment,
        "image_url": f"/api/images/{filename}",
        "research_note": "AI screening result only. Confirm diagnosis with an agricultural expert."
    }

@app.get("/api/scans")
def list_scans(limit: int = 100):
    limit = max(1, min(limit, 500))
    with db() as con:
        rows = con.execute("""
            SELECT id, created_at, crop, disease, confidence, result_status,
                   sample_code, observer, notes, image_filename
            FROM scans ORDER BY created_at DESC LIMIT ?
        """, (limit,)).fetchall()
    return [dict(row) for row in rows]

@app.get("/api/stats")
def stats():
    with db() as con:
        total = con.execute("SELECT COUNT(*) FROM scans").fetchone()[0]
        crops = con.execute("SELECT crop, COUNT(*) AS count FROM scans GROUP BY crop ORDER BY count DESC").fetchall()
        diseases = con.execute("SELECT disease, COUNT(*) AS count FROM scans GROUP BY disease ORDER BY count DESC LIMIT 8").fetchall()
    return {"total_scans": total, "by_crop": [dict(x) for x in crops], "top_diseases": [dict(x) for x in diseases]}

@app.get("/api/export.csv")
def export_csv():
    with db() as con:
        rows = con.execute("""
            SELECT id, created_at, crop, disease, confidence, result_status,
                   sample_code, observer, notes, image_filename
            FROM scans ORDER BY created_at DESC
        """).fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["scan_id", "created_at_utc", "crop", "predicted_disease", "confidence",
                     "provider_result", "sample_code", "observer", "notes", "image_filename"])
    for row in rows:
        writer.writerow(list(row))
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=plantcare_research_dataset.csv"}
    )

@app.get("/api/images/{filename}")
def get_image(filename: str):
    if not re.fullmatch(r"[a-f0-9-]{36}\.(jpg|png|webp)", filename):
        raise HTTPException(status_code=400, detail="Invalid image filename.")
    path = UPLOAD_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Image not found.")
    return FileResponse(path)
