
import asyncio
import csv
import io
import json
import logging
import os
import re
import sqlite3
import uuid

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from app.dataset import CLASSES
from app.local_model import predict_image


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]

DB_PATH = Path(
    os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "plantcare.db"))
)

UPLOAD_DIR = Path(
    os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads"))
)

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "8"))

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "*").split(",")
    if origin.strip()
]

DB_PATH.parent.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("plantcare")


# --------------------------------------------------
# FASTAPI APPLICATION
# --------------------------------------------------

app = FastAPI(
    title="PlantCare AI Research API",
    version="3.1.0",
    description="CPU-based plant disease screening and research history."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS or ["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# --------------------------------------------------
# DATABASE CONNECTION
# --------------------------------------------------

@contextmanager
def get_db():
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row

    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db():
    with get_db() as con:
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


# --------------------------------------------------
# ROOT AND HEALTH
# --------------------------------------------------

@app.get("/")
def root():
    return {
        "service": "PlantCare AI Research API",
        "status": "ok",
        "version": "3.1.0"
    }


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "PlantCare AI",
        "model": "EfficientNet-B4",
        "classes": len(CLASSES),
        "storage": "sqlite",
        "device": "cpu"
    }


# --------------------------------------------------
# PLANT DIAGNOSIS
# --------------------------------------------------

@app.post("/api/diagnose")
async def diagnose(
    image: UploadFile = File(...),
    crop: str = Form(...),
    sample_code: str = Form(""),
    observer: str = Form(""),
    notes: str = Form("")
):

    selected_crop = crop.strip().casefold()

    supported_crops = {
        "apple", "bell pepper", "blueberry", "cherry",
        "corn (maize)", "grape", "orange", "peach",
        "potato", "raspberry", "soybean", "squash",
        "strawberry", "tomato"
    }

    if selected_crop not in supported_crops:
        raise HTTPException(
            status_code=400,
            detail="Please select one of the 14 supported crops."
        )

    content_types = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp"
    }

    if image.content_type not in content_types:
        raise HTTPException(
            status_code=415,
            detail="Upload a JPG, PNG, or WebP image."
        )

    raw = await image.read(MAX_UPLOAD_MB * 1024 * 1024 + 1)

    if not raw:
        raise HTTPException(
            status_code=400,
            detail="The uploaded image is empty."
        )

    if len(raw) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"Image must be smaller than {MAX_UPLOAD_MB} MB."
        )

    # Run CPU inference without blocking the API event loop.
    try:
        prediction = await asyncio.to_thread(predict_image, raw)

    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        ) from exc

    except Exception as exc:
        logger.exception("Model inference failed")

        raise HTTPException(
            status_code=503,
            detail="The local AI model is temporarily unavailable."
        ) from exc

    predicted_crop = prediction["crop"].strip()

    # Do not save a scan when the selected crop and
    # model-predicted crop do not match.
    if predicted_crop.casefold() != selected_crop:

        alternatives = prediction.get("top_predictions", [])

        alternative_text = "; ".join(
            f"{item['crop']} - {item['disease']} "
            f"({item['confidence']}%)"
            for item in alternatives
        )

        raise HTTPException(
            status_code=422,
            detail=(
                f"Crop mismatch: you selected {crop}, but the model's "
                f"top prediction is {predicted_crop}. "
                f"Top predictions: {alternative_text}. "
                "Please check the crop selection and image. "
                "Do not change the crop selection just to force a result."
            )
        )

    # --------------------------------------------------
    # SAVE RESEARCH RECORD
    # --------------------------------------------------

    scan_id = str(uuid.uuid4())

    created_at = datetime.now(timezone.utc).isoformat()

    suffix = content_types[image.content_type]

    filename = f"{scan_id}{suffix}"

    image_path = UPLOAD_DIR / filename

    class_name = prediction["class_name"]

    status = (
        "healthy"
        if "healthy" in class_name.casefold()
        else "disease_detected"
    )

    saved = False

    try:
        image_path.write_bytes(raw)
        saved = True

        with get_db() as con:
            con.execute("""
                INSERT INTO scans (
                    id, created_at, crop, disease, confidence,
                    result_status, sample_code, observer, notes,
                    image_filename, provider_response
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                scan_id,
                created_at,
                predicted_crop,
                prediction["disease"],
                prediction["confidence"],
                status,
                sample_code.strip(),
                observer.strip(),
                notes.strip(),
                filename,
                json.dumps(prediction, ensure_ascii=False)
            ))

    except Exception as exc:

        if saved:
            image_path.unlink(missing_ok=True)

        logger.exception("Could not save scan")

        raise HTTPException(
            status_code=500,
            detail="Diagnosis completed, but the research record could not be saved."
        ) from exc

    # --------------------------------------------------
    # API RESPONSE
    # --------------------------------------------------

    return {
        "id": scan_id,
        "created_at": created_at,
        "crop": predicted_crop,
        "disease": prediction["disease"],
        "confidence": prediction["confidence"],
        "result_status": status,
        "severity": prediction["severity"],
        "pathogen": prediction["pathogen"],
        "treatment": {
            "cure": prediction["treatment"]
        },
        "model": "EfficientNet-B4",
        "device": "cpu",
        "top_predictions": prediction.get("top_predictions", []),
        "prediction_status": prediction.get(
            "prediction_status", "screening_result"
        ),
        "warning": prediction.get("warning", ""),
        "confidence_note": prediction.get("confidence_note", ""),
        "image_url": f"/api/images/{filename}",
        "research_note": (
            "AI screening only. This result is not a confirmed diagnosis; "
            "consult an agricultural expert before treatment."
        )
    }


# --------------------------------------------------
# SCAN HISTORY
# --------------------------------------------------

@app.get("/api/scans")
def list_scans(limit: int = 100):

    limit = max(1, min(limit, 500))

    with get_db() as con:
        rows = con.execute("""
            SELECT id, created_at, crop, disease, confidence,
                   result_status, sample_code, observer, notes,
                   image_filename
            FROM scans
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,)).fetchall()

    return [dict(row) for row in rows]


# --------------------------------------------------
# RESEARCH DASHBOARD
# --------------------------------------------------

@app.get("/api/stats")
def stats():

    with get_db() as con:

        total = con.execute(
            "SELECT COUNT(*) FROM scans"
        ).fetchone()[0]

        crops = con.execute("""
            SELECT crop, COUNT(*) AS count
            FROM scans
            GROUP BY crop
            ORDER BY count DESC
        """).fetchall()

        diseases = con.execute("""
            SELECT disease, COUNT(*) AS count
            FROM scans
            GROUP BY disease
            ORDER BY count DESC
            LIMIT 8
        """).fetchall()

    return {
        "total_scans": total,
        "by_crop": [dict(row) for row in crops],
        "top_diseases": [dict(row) for row in diseases]
    }


# --------------------------------------------------
# CSV EXPORT
# --------------------------------------------------

@app.get("/api/export.csv")
def export_csv():

    with get_db() as con:
        rows = con.execute("""
            SELECT id, created_at, crop, disease, confidence,
                   result_status, sample_code, observer, notes,
                   image_filename
            FROM scans
            ORDER BY created_at DESC
        """).fetchall()

    output = io.StringIO()

    writer = csv.writer(output)

    writer.writerow([
        "scan_id", "created_at", "crop", "disease",
        "confidence", "result_status", "sample_code",
        "observer", "notes", "image_filename"
    ])

    for row in rows:
        writer.writerow(list(row))

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition":
            "attachment; filename=plantcare_research_data.csv"
        }
    )


# --------------------------------------------------
# IMAGE ACCESS
# --------------------------------------------------

@app.get("/api/images/{filename}")
def get_image(filename: str):

    if not re.fullmatch(
        r"[a-f0-9-]{36}\.(jpg|png|webp)",
        filename
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid image filename."
        )

    path = UPLOAD_DIR / filename

    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Image not found."
        )

    return FileResponse(path)
