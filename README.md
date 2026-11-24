# 🌾 EPICS Farm Scouting AI System

**VIT Bhopal EPICS Project** — AI-Based Farm Scouting, Soil Health & Fertilizer Recommendation System using Sentinel-2 satellite imagery via Google Earth Engine.

## 🚀 What This Does

- **Satellite Analysis** — Queries Sentinel-2 imagery via Google Earth Engine to compute NDVI (vegetation), NDMI (moisture), and NDRE (chlorophyll/nitrogen proxy) indices for a given farm field.
- **AI Anomaly Detection** — Uses an Isolation Forest ML model to detect stressed zones ("hotspots") within the field.
- **Fertilizer Recommendations** — Rules-based engine maps vegetation/moisture signatures to actionable NPK recommendations, flagged for ground-truth validation.
- **Interactive Dashboard** — React frontend with Google Satellite map, live health scores, hotspot visualization, and soil data entry.

---

## 🏗️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React + TypeScript + Vite + Leaflet |
| Backend | FastAPI (Python) + SQLAlchemy + SQLite |
| Satellite | Google Earth Engine Python API (Sentinel-2 L2A) |
| ML | scikit-learn Isolation Forest |
| Map | Leaflet + react-leaflet + Google Satellite tiles |

---

## ⚙️ Setup Instructions

### Prerequisites
- Python 3.11+
- Node.js 18+
- Google Earth Engine account (authenticated via `earthengine authenticate`)

### 1. Clone the repo
```bash
git clone https://github.com/YOUR_USERNAME/EPICS.git
cd EPICS
```

### 2. Backend setup
```bash
cd backend
pip install -r requirements.txt
```

Create a `.env` file in the root `EPICS/` folder (copy from `.env.example`):
```bash
cp .env.example .env
# Edit .env and set your GEE_PROJECT_ID
```

Authenticate with Google Earth Engine:
```bash
earthengine authenticate
```

Initialize the database:
```bash
cd ..
python -c "from backend.database import init_db; init_db()"
```

### 3. Frontend setup
```bash
cd frontend
npm install
```

### 4. Run the app

**Terminal 1 — Backend:**
```bash
cd EPICS
$env:PYTHONPATH = "C:\path\to\EPICS"   # Windows PowerShell
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 — Frontend:**
```bash
cd EPICS/frontend
npm run dev
```

Open **http://localhost:5173** in your browser.

---

## 📁 Project Structure

```
EPICS/
├── backend/
│   ├── api/              # FastAPI route handlers
│   ├── models/           # SQLAlchemy ORM models
│   ├── services/
│   │   ├── gee_service.py          # Google Earth Engine integration
│   │   ├── anomaly_detector.py     # Isolation Forest ML model
│   │   └── recommendation_service.py  # NPK rules engine
│   ├── config.py         # App settings (reads from .env)
│   ├── database.py       # DB init & session
│   └── main.py           # FastAPI app entry point
├── frontend/
│   ├── src/
│   │   ├── components/   # React components (Map, Cards, etc.)
│   │   ├── pages/        # Dashboard, FarmMap, Hotspots, SoilData
│   │   ├── services/     # API client functions
│   │   └── types/        # TypeScript type definitions
│   └── vite.config.ts
├── .env.example          # Template — copy to .env and fill in
├── .gitignore
└── README.md
```

---

## 🌍 Google Earth Engine — DEMO vs LIVE mode

| Mode | Setting in `.env` | What it does |
|---|---|---|
| Demo (default) | `DEMO_MODE=True` | Uses simulated NDVI/NDMI/NDRE data. No GEE account needed. |
| Live | `DEMO_MODE=False` + `GEE_PROJECT_ID=your-project` | Queries real Sentinel-2 imagery from GEE. Requires `earthengine authenticate`. |

> **Note:** Satellites cannot directly measure soil N, P, K, or pH. Fertilizer recommendations from satellite data alone must be validated with physical soil tests.

---

## 👥 Team

VIT Bhopal — EPICS Cohort 2026
