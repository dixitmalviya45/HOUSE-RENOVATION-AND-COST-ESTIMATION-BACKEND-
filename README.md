# HOUSE-RENOVATION-AND-COST-ESTIMATION-BACKEND-

FastAPI backend for **E2M** — AI-based exterior house renovation and cost estimation.

Pairs with the frontend repo: [HOUSE-RENOVATION-AND-COST-ESTIMATION-FRONTEND-](https://github.com/dixitmalviya45/HOUSE-RENOVATION-AND-COST-ESTIMATION-FRONTEND-).

## Stack

Python 3.11+ FastAPI, Beanie/Motor, JWT, OpenCV, Roboflow, Gemini, Cloudinary, ReportLab.

Pinned for hosting: **Python 3.12** (see `.python-version`). Render’s default can be 3.14; 3.12 is more reliable with MongoDB Atlas TLS and native wheels.

## Local setup

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
Health: http://localhost:8000/health  
Materials auto-seed on first startup.

---

## Deploy on Render

This repo is set up as a Render **Web Service** (blueprint in `render.yaml`).

### 1. MongoDB Atlas

Render cannot reach `localhost`. Use Atlas:

1. Create a free M0 cluster.
2. Database user + password (URL-encode special characters in the URI).
3. **Network Access → Add IP → `0.0.0.0/0`** (Render outbound IPs are dynamic).
4. Connection string **must include the database name**:

```
mongodb+srv://USER:PASSWORD@cluster.mongodb.net/e2m_db?retryWrites=true&w=majority
```

### 2. Create the Web Service

**New → Web Service → this GitHub repo.**

| Setting | Value |
|---|---|
| Language | Python 3 |
| Region | any |
| Instance | Free |
| Build command | `pip install -r requirements.txt` |
| Start command | `bash start.sh` |
| Health check path | `/health` |

Or import `render.yaml` as a Render Blueprint. Secrets marked `sync: false` must be filled in the dashboard.

Equivalent start command (if you skip `start.sh`):

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'
```

Do **not** use `--reload` on Render. Bind `0.0.0.0` and `$PORT` (Render injects `PORT`).

### 3. Environment variables

Set these in **Render → Environment**:

| Key | Required | Notes |
|---|---|---|
| `APP_ENV` | yes | `production` |
| `MONGODB_URI` | yes | Atlas URI with `/e2m_db` |
| `JWT_SECRET_KEY` | yes | Long random string (32+ chars). Not the example placeholder. |
| `JWT_ALGORITHM` | no | `HS256` |
| `JWT_EXPIRY_MINUTES` | no | `1440` |
| `CORS_ORIGINS` | yes | Your Vercel URL, e.g. `https://your-app.vercel.app` (no trailing slash) |
| `CLOUDINARY_CLOUD_NAME` | for upload | |
| `CLOUDINARY_API_KEY` | for upload | |
| `CLOUDINARY_API_SECRET` | for upload | |
| `GEMINI_API_KEY` | for AI redesign | Falls back to local tint if unavailable |
| `ROBOFLOW_API_KEY` | optional | OpenCV fallback if unset |
| `ROBOFLOW_MODEL` | no | `door-window-detection/1` |
| `PYTHON_VERSION` | no | `3.12.8` (also set via `.python-version`) |
| `PYTHONUNBUFFERED` | no | `1` (live logs) |

Startup **fails on purpose** in production if `JWT_SECRET_KEY` is still a placeholder or `MONGODB_URI` points at localhost.

### 4. After deploy

- API: `https://e2m-backend.onrender.com` (your service URL)
- Docs: `https://<service>.onrender.com/docs`
- Health: `https://<service>.onrender.com/health`

On the **frontend** (Vercel), set:

```
VITE_API_BASE_URL=https://<your-render-service>.onrender.com/api
```

`CORS_ORIGINS` on Render must match the Vercel origin exactly. Preview deploys (`*.vercel.app`) are allowed via `CORS_ORIGIN_REGEX`.

### 5. Free-tier behavior

- Instances **spin down** after idle time; the first request can take 30–60s.
- HTTP timeout is about **100s** — Gemini redesigns can be slow; a local fallback still returns an image if Gemini fails.
- OpenCV uses `opencv-python-headless` plus `Aptfile` system libs (`libgl1`, `libglib2.0-0`, …).

---

## Hosting files

| File | Purpose |
|---|---|
| `render.yaml` | Render Blueprint (build/start/health/env) |
| `start.sh` | Bind `0.0.0.0:$PORT`, proxy headers |
| `.python-version` | Python 3.12 |
| `Aptfile` | OpenCV runtime libraries on Render |
| `.gitattributes` | LF line endings for `start.sh` |
| `/health` | Liveness probe |

---

## License

Educational / assessment project.
