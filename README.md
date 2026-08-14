# HOUSE-RENOVATION-AND-COST-ESTIMATION-BACKEND-

FastAPI backend for E2M — AI-based exterior house renovation and cost estimation.

Pairs with the frontend repo: [HOUSE-RENOVATION-AND-COST-ESTIMATION-FRONTEND-](https://github.com/dixitmalviya45/HOUSE-RENOVATION-AND-COST-ESTIMATION-FRONTEND-).

## Stack

Python 3.11+ FastAPI, Beanie/Motor, JWT, OpenCV, Roboflow, Gemini, Cloudinary, ReportLab.

## Setup

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your keys.

MongoDB (local Docker recommended on Windows / Python 3.14):

```bash
docker run -d --name e2m-mongo -p 27017:27017 mongo:7
```

```
MONGODB_URI=mongodb://localhost:27017/e2m_db
```

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: http://localhost:8000/docs  
Materials auto-seed on first startup.
