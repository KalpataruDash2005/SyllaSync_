# SyllabSync — Production-Ready Setup Guide

Upload 10–20 course PDFs → AI extracts & organises content → generates a
personalised 15-week study plan with memory techniques → syncs to Google Calendar
and sends weekly prep emails via n8n.

---

## Architecture

```
Browser (HTML/CSS/JS)
      │ POST /api/upload  (multipart, up to 20 × 50 MB PDFs)
      ▼
FastAPI Backend (Python)
  ├─ pdf_processor.py   — PyMuPDF text extraction + smart truncation
  ├─ gemini_client.py   — Gemini 1.5 Flash (2-pass: summarise → plan)
  └─ main.py            — SSE progress stream, job store, static file server
      │ POST N8N_WEBHOOK_URL  (study plan JSON)
      ▼
n8n Workflow (18 nodes, 3 lanes)
  ├─ Lane 1: Receive plan → send reviewer preview email
  ├─ Lane 2: Approve → 15 Google Calendar events + Week-1 student email
  │          Reject  → self-learning loop (Gemini distils improvement rule)
  └─ Lane 3: Every Monday 8AM → send that week's prep email automatically
```

---

## Quick Start (local)

### 1. Clone & configure

```bash
git clone <your-repo>
cd syllabsync/backend
cp .env.example .env
# Edit .env — fill GEMINI_API_KEY at minimum
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the server

```bash
python main.py
# Server starts at http://localhost:8000
```

Open **http://localhost:8000** in your browser — the frontend loads automatically.

---

## Docker (recommended for production)

```bash
# 1. Copy and fill env
cp backend/.env.example .env

# 2. Build & run
docker compose up --build -d

# 3. Check health
curl http://localhost:8000/api/health
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | ✅ | Free from aistudio.google.com |
| `N8N_WEBHOOK_URL` | Optional | n8n webhook URL for calendar/email sync |
| `STUDENT_EMAIL` | n8n only | Email to receive weekly plans |
| `REVIEWER_EMAIL` | n8n only | Email to approve/reject plans |
| `MAX_FILE_SIZE_MB` | Default: 50 | Max PDF size in MB |
| `MAX_FILES` | Default: 20 | Max PDFs per upload |
| `SEMESTER_START_DATE` | n8n only | ISO date, e.g. `2025-08-01` |
| `TIMEZONE` | n8n only | e.g. `Asia/Kolkata` |

---

## n8n Workflow Setup

### Import
1. Open n8n → **Workflows → Add → Import from File**
2. Upload `n8n/syllabsync_production.json`

### Environment Variables (Settings → Variables)
Add all variables from the table above.

### Credentials (Settings → Credentials)
1. **Gmail OAuth2** — Connect your Google account
2. **Google Calendar OAuth2** — Same or different Google account

### Webhook URLs
After importing, copy the two webhook URLs from the n8n interface:
- `POST /syllabsync-ingest` → set as `N8N_WEBHOOK_URL` in `.env`
- `GET /syllabsync-decide` → used internally (auto-built in email buttons)

### Test
1. Upload PDFs via http://localhost:8000
2. Wait for processing (watch SSE progress bar)
3. Check **REVIEWER_EMAIL** for the plan preview email
4. Click **Approve** → check Google Calendar + **STUDENT_EMAIL**

---

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/upload` | POST | Upload PDFs, returns `job_id` |
| `/api/progress/{job_id}` | GET (SSE) | Real-time progress stream |
| `/api/result/{job_id}` | GET | Fetch completed study plan JSON |
| `/api/health` | GET | Health check + active job count |
| `/` | GET | Serves the frontend |

### Upload example (curl)
```bash
curl -X POST http://localhost:8000/api/upload \
  -F "files=@syllabus.pdf" \
  -F "files=@lecture_notes.pdf"
# Returns: { "job_id": "...", "status": "queued", "file_count": 2 }
```

### Progress (SSE)
```bash
curl -N http://localhost:8000/api/progress/{job_id}
# Streams: data: {"status":"processing","progress":45,"step":"AI analysis pass 1/2..."}
```

---

## n8n Workflow Lanes

### Lane 1 — Ingest (triggered by Python backend)
```
Webhook (POST /syllabsync-ingest)
  → Parse Plan + Build Preview  [stores plan in static data]
  → Gmail: Send preview to reviewer
  → Respond: 200 OK to Python
```

### Lane 2 — Human Decision (triggered by reviewer clicking email button)
```
Webhook (GET /syllabsync-decide?sid=...&a=approve|reject)
  → IF approved?
      YES → Load Plan + Build Week-1 Email
              → Gmail: Send to student
              → Split 15 events → Google Calendar: Create Event × 15
              → Respond: Green success page
      NO  → Store Rejection + Build Learning Prompt
              → Gemini: Distil improvement rule
              → Save rule (injected into next plan's prompt)
              → Respond: Amber feedback page
```

### Lane 3 — Weekly Automation (every Monday 8AM)
```
Schedule Trigger (0 8 * * 1)
  → Build Weekly Prep Email  [auto-determines current week]
  → Gmail: Send to student
```

### Self-Learning Loop
Every rejection → feedback stored → Gemini distils a rule →
rule saved in static data → next plan's n8n email includes the rule.
Plans improve automatically over time.

---

## File Limits

- **Per file**: up to 50 MB
- **Per request**: up to 20 files (1 GB total)
- **Text extracted**: up to 80,000 chars per PDF (intelligent sampling for larger files)
- **Gemini context**: combined summary stays under model limits via 2-pass approach

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `GEMINI_API_KEY not set` | Add key to `.env` and restart |
| Upload timeout | Increase uvicorn `timeout_keep_alive` in `main.py` |
| Gemini rate limit (429) | Wait 1 min — free tier is 15 req/min. Tenacity retries automatically |
| n8n webhook not called | Check `N8N_WEBHOOK_URL` is correct and n8n is running |
| Google Calendar events not created | Re-authenticate Google Calendar OAuth2 in n8n |
| PDF text empty | File may be scanned/image-only — use OCR pre-processing |

P.S. The code will run perfectly but it'll not be seen to you, because the email are our developers so due to time constraint we can't add the feature for your own mail address
