import asyncio
import logging
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.dataset import CLASSES
from app.local_model import predict_image

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("plantcare")

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "8"))
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "*").split(",")
    if origin.strip()
]

app = FastAPI(
    title="PlantCare AI API",
    version="2.0.0",
    description="Stateless plant-leaf disease screening using the trained EfficientNet-B4 model.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS or ["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"service": "PlantCare AI API", "status": "ok", "health": "/api/health"}


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "PlantCare AI",
        "model": "EfficientNet-B4",
        "classes": len(CLASSES),
        "storage": "stateless",
    }


@app.post("/api/diagnose")
async def diagnose(
    image: UploadFile = File(...),
    crop: str = Form(...),
):
    selected_crop = crop.strip().casefold()
    supported_crops = {
        "apple", "bell pepper", "blueberry", "cherry", "corn (maize)",
        "grape", "orange", "peach", "potato", "raspberry", "soybean",
        "squash", "strawberry", "tomato",
    }

    if selected_crop not in supported_crops:
        raise HTTPException(
            status_code=400,
            detail="Unsupported crop. Please choose one of the 14 crops supported by this model.",
        )

    if image.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(
            status_code=415,
            detail="Upload a JPG, PNG, or WebP leaf image.",
        )

    raw = await image.read()
    if not raw:
        raise HTTPException(status_code=400, detail="The uploaded image is empty.")
    if len(raw) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"Image must be smaller than {MAX_UPLOAD_MB} MB.",
        )

    try:
        prediction = await asyncio.to_thread(predict_image, raw)
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail="The image could not be read. Please upload a clear JPG, PNG, or WebP leaf photo.",
        ) from exc
    except Exception as exc:
        logger.exception("Model inference failed")
        raise HTTPException(
            status_code=503,
            detail="The AI model is temporarily unavailable. Please try again shortly.",
        ) from exc

    predicted_crop = prediction["crop"].strip()
    if predicted_crop.casefold() != selected_crop:
        raise HTTPException(
            status_code=422,
            detail=(
                f"The model detected {predicted_crop}, but you selected {crop}. "
                "Please select the matching crop and try again."
            ),
        )

    class_name = prediction["class_name"]
    status = "healthy" if "healthy" in class_name.casefold() else "disease_detected"

    # Stateless response: no scan limit, database, uploaded-file storage, or history.
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "crop": predicted_crop,
        "disease": prediction["disease"],
        "confidence": prediction["confidence"],
        "result_status": status,
        "severity": prediction["severity"],
        "pathogen": prediction["pathogen"],
        "treatment": {"cure": prediction["treatment"]},
        "model": "EfficientNet-B4",
        "research_note": (
            "AI screening only. This result is not a confirmed diagnosis; "
            "consult an agricultural expert before treatment."
        ),
    }
