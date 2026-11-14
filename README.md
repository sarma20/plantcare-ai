# PlantCare AI — Plant Disease Detection & Research System

A web + Android-ready research app for photographing crop leaves, sending images to an online disease-detection API, viewing the result, saving scan records, and exporting a research dataset.

## Important research note
This project does **not** fabricate diagnoses. Real disease detection requires a valid PlantHealthEngine API key. Until the key is configured, the backend returns a clear setup error. AI predictions are screening results, not a substitute for confirmation by an agricultural expert.

The app stores submitted images and scan metadata in a local SQLite database on the server. Protect the server and obtain consent before collecting identifiable or location-linked data.

## Stack
- Frontend: React + Vite
- Android wrapper: Capacitor
- Backend: Python + FastAPI
- Research records: SQLite
- Disease inference: PlantHealthEngine API (`POST https://planthealthengine.com/api/v1/diagnose`)

API docs: https://planthealthengine.com/docs

## 1. Requirements
- Node.js 20+
- Python 3.10+
- Android Studio (only for Android APK)
- PlantHealthEngine API key

## 2. Configure the backend
Open a terminal in `backend/`:

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your API key:

```env
PLANT_HEALTH_API_KEY=YOUR_REAL_API_KEY
PLANT_HEALTH_API_URL=https://planthealthengine.com/api/v1/diagnose
DATABASE_PATH=./data/plantcare.db
UPLOAD_DIR=./uploads
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

Start the API:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API health: http://localhost:8000/api/health  
Interactive API docs: http://localhost:8000/docs

## 3. Run the web app
Open a second terminal in `frontend/`:

```bash
npm install
```

Create `.env` from `.env.example`. For local development:

```env
VITE_API_BASE_URL=http://localhost:8000
```

Start:

```bash
npm run dev
```

Open http://localhost:5173

## 4. Build Android app
The same responsive frontend is wrapped with Capacitor.

From `frontend/`:

```bash
npm install
npm run build
npx cap add android
npx cap sync android
npx cap open android
```

In Android Studio, connect a device or start an emulator and press **Run**. To create an APK, use **Build > Build Bundle(s) / APK(s) > Build APK(s)**.

### Set the production backend URL
Before building the Android app, set `VITE_API_BASE_URL` in `frontend/.env` to your deployed HTTPS backend, for example:

```env
VITE_API_BASE_URL=https://YOUR-BACKEND-DOMAIN
```

Then run `npm run build` and `npx cap sync android` again. Do not use `localhost` on a physical Android phone; it refers to the phone itself.

Deploy the backend to a Python host that supports persistent storage, or replace SQLite/local uploads with managed database/object storage before multi-user production use.

## 5. Research workflow
1. Select the crop.
2. Capture a clear photo of one affected leaf/plant.
3. Submit the image.
4. Review the disease prediction, confidence, and guidance returned by the API.
5. Add optional sample code, location/field notes, and observer details.
6. Use **Research data** to review records and download CSV.

The CSV contains scan ID, timestamp, crop, diagnosis, confidence, sample code, observer, notes, and image filename. Image files remain in the backend `uploads/` folder.

## 6. Supported crops
The UI includes common crop choices (rice, tomato, potato, maize, chilli, cotton, soybean, wheat, other). The API provider may support a different crop list; check its current documentation and account plan. Unsupported crop values may be rejected by the provider.

## 7. Research quality and limitations
- Keep original images and record capture conditions consistently.
- Collect healthy and diseased samples across multiple fields, crop stages, lighting conditions, and devices.
- Ask an agricultural expert to verify a subset of labels.
- Report precision, recall, F1-score, confusion matrix, and sample counts in your paper.
- Do not interpret API confidence as calibrated probability unless the provider documents that meaning.
- Provider treatment guidance may not be locally approved for Assam/India. Verify any pesticide or treatment advice with local agricultural extension services and product labels.
- Add authentication, HTTPS, access controls, consent, retention rules, backups, and secure cloud storage before real public deployment.

## Project structure
```text
plantcare-ai/
  backend/
    app/main.py
    .env.example
    requirements.txt
  frontend/
    src/App.jsx
    src/main.jsx
    src/styles.css
    index.html
    package.json
    capacitor.config.json
    .env.example
```
