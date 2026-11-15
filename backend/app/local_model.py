
from pathlib import Path
from io import BytesIO
import warnings

import torch
from PIL import Image, ImageOps, UnidentifiedImageError

from app.model import EfficientNetB4Classifier
from app.dataset import CLASSES, get_transforms, prepare_input_image
from app.diseases import get_disease_info, display_name


# --------------------------------------------------
# CONFIGURATION: CPU ONLY
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[1]
MODEL_PATH = BASE_DIR / "models" / "best_model.pth"

DEVICE = torch.device("cpu")
IMAGE_SIZE = 224

MAX_IMAGE_PIXELS = 25_000_000
MIN_IMAGE_SIDE = 64

# These are screening warning thresholds, not
# scientifically calibrated confidence thresholds.
LOW_CONFIDENCE_THRESHOLD = 60.0
LOW_MARGIN_THRESHOLD = 8.0


# --------------------------------------------------
# LOAD MODEL
# --------------------------------------------------

def load_model():
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(
            f"Model checkpoint not found: {MODEL_PATH}"
        )

    checkpoint = torch.load(
        MODEL_PATH,
        map_location="cpu",
        weights_only=False
    )

    model = EfficientNetB4Classifier(
        num_classes=len(CLASSES),
        dropout=0.4,
        pretrained=False,
    )

    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(DEVICE)
    model.eval()

    return model


model = load_model()
transform = get_transforms("val", IMAGE_SIZE)


# --------------------------------------------------
# IMAGE VALIDATION
# --------------------------------------------------

def prepare_uploaded_image(image_bytes: bytes):
    if not image_bytes:
        raise ValueError("The uploaded image is empty.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter(
                "error",
                Image.DecompressionBombWarning
            )

            image = Image.open(BytesIO(image_bytes))

            if image.format not in {"JPEG", "PNG", "WEBP"}:
                raise ValueError(
                    "Please upload a JPG, PNG, or WebP image."
                )

            width, height = image.size

            if width < MIN_IMAGE_SIDE or height < MIN_IMAGE_SIDE:
                raise ValueError(
                    "Image is too small. Please upload a clearer image."
                )

            if width * height > MAX_IMAGE_PIXELS:
                raise ValueError(
                    "Image dimensions are too large."
                )

            image.load()
            image = ImageOps.exif_transpose(image).convert("RGB")

    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning
    ) as exc:
        raise ValueError(
            "Invalid or unsafe image. Please upload a valid leaf photo."
        ) from exc

    return prepare_input_image(image, IMAGE_SIZE)


# --------------------------------------------------
# PREDICTION
# --------------------------------------------------

def predict_image(image_bytes: bytes) -> dict:
    """Predict a PlantVillage class using CPU inference."""

    image = prepare_uploaded_image(image_bytes)

    tensor = transform(image).unsqueeze(0).to(DEVICE)

    with torch.inference_mode():
        logits = model(tensor)
        probabilities = torch.softmax(logits, dim=1)[0]

    top_values, top_indices = torch.topk(
        probabilities,
        k=min(3, len(CLASSES))
    )

    top_predictions = []

    for score, index in zip(top_values, top_indices):
        class_name = CLASSES[index.item()]
        info = get_disease_info(class_name)

        top_predictions.append({
            "class_name": class_name,
            "crop": info["plant"],
            "disease": display_name(class_name),
            "confidence": round(score.item() * 100, 2)
        })

    # Main prediction
    best = top_predictions[0]
    info = get_disease_info(best["class_name"])

    confidence = best["confidence"]

    if len(top_predictions) > 1:
        margin = confidence - top_predictions[1]["confidence"]
    else:
        margin = confidence

    # Conservative warning based on model output.
    # This does NOT prove whether an image is supported.
    needs_review = (
        confidence < LOW_CONFIDENCE_THRESHOLD
        or margin < LOW_MARGIN_THRESHOLD
    )

    if needs_review:
        prediction_status = "review_recommended"
        warning = (
            "The model is uncertain about this result. "
            "Please review the top predictions and consult "
            "an agricultural expert."
        )
    else:
        prediction_status = "screening_result"
        warning = (
            "This is an AI screening result, not a confirmed "
            "plant disease diagnosis."
        )

    return {
        "class_name": best["class_name"],
        "crop": info["plant"],
        "disease": display_name(best["class_name"]),
        "confidence": confidence,
        "severity": info["severity"],
        "pathogen": info["pathogen"],
        "treatment": info["treatment"],
        "device": "cpu",
        "top_predictions": top_predictions,
        "prediction_status": prediction_status,
        "warning": warning,
        "confidence_note": (
            "Confidence is the model's softmax score. "
            "It is not a measure of real-world accuracy."
        )
    }
