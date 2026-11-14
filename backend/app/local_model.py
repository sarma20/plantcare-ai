
from pathlib import Path
from io import BytesIO

import torch
from PIL import Image, ImageOps

from app.model import EfficientNetB4Classifier
from app.dataset import CLASSES, get_transforms, prepare_input_image
from app.diseases import get_disease_info, display_name

BASE_DIR = Path(__file__).resolve().parents[1]
MODEL_PATH = BASE_DIR / "models" / "best_model.pth"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
IMAGE_SIZE = 224

# Load the trained model once when the backend starts.
def load_model():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model checkpoint not found: {MODEL_PATH}")

    checkpoint = torch.load(MODEL_PATH, map_location=DEVICE)

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


def predict_image(image_bytes: bytes) -> dict:
    """Predict a PlantVillage disease from uploaded image bytes."""

    try:
        image = Image.open(BytesIO(image_bytes))
        image = ImageOps.exif_transpose(image).convert("RGB")
    except Exception as exc:
        raise ValueError("The uploaded file is not a valid image.") from exc

    image = prepare_input_image(image, IMAGE_SIZE)
    tensor = transform(image).unsqueeze(0).to(DEVICE)

    with torch.inference_mode():
        logits = model(tensor)
        probabilities = torch.softmax(logits, dim=1)[0]

    confidence, predicted_index = torch.max(probabilities, dim=0)

    class_name = CLASSES[predicted_index.item()]
    info = get_disease_info(class_name)

    return {
        "class_name": class_name,
        "crop": info["plant"],
        "disease": display_name(class_name),
        "confidence": round(confidence.item() * 100, 2),
        "severity": info["severity"],
        "pathogen": info["pathogen"],
        "treatment": info["treatment"],
        "device": str(DEVICE),
    }
