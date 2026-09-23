# RUN GUIDE

## 1. Clone Repository

```bash
git clone <repository-url>
cd GYMM
```

---

## 2. Create Virtual Environment

### macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
```

### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

---

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 4. Configure Environment Variables

Create a `.env` file in the project root.

```env
GROQ_API_KEY=your_groq_api_key
```

---

## 5. Start the Application

```bash
uvicorn main:app --reload
```

Server will start at:

```text
http://127.0.0.1:8000
```

---

## 6. Open API Documentation

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

ReDoc:

```text
http://127.0.0.1:8000/redoc
```

---

## 7. Sample API Request

### Endpoints

```http
POST   /api/v1/sessions                              # create session (optional initial profile)
PATCH  /api/v1/sessions/{session_id}/profile         # merge profile fields
POST   /api/v1/sessions/{session_id}/chat/stream     # chat turn (SSE), body: {"message": "..."}
GET    /api/v1/sessions/{session_id}/state           # runtime state (debug)
DELETE /api/v1/sessions/{session_id}                 # clear session
GET    /health
```

### Example

```bash
SID=$(curl -s -X POST http://127.0.0.1:8000/api/v1/sessions -H 'Content-Type: application/json' \
  -d '{"profile": {"age": 25, "gender": "male", "weight_kg": 80, "height_cm": 176, "activity_level": "moderately_active"}}' \
  | python3 -c 'import sys, json; print(json.load(sys.stdin)["session_id"])')

curl -N -X POST http://127.0.0.1:8000/api/v1/sessions/$SID/chat/stream -H 'Content-Type: application/json' \
  -d '{"message": "Create a complete fat loss plan"}'
```

The profile lives in the session (LangGraph checkpoint, `thread_id == session_id`), so chat
requests only send the message. The final `done` event's `status` is one of
`success | needs_input | incomplete | error`.

---

## 8. Expected Flow

```text
User message
      │
      ▼
Planner (goal + success criteria + validated task plan)
      │
      ▼
Executor ──decide──> worker (bmi / water / macros / diet / workout / gym / general)
   ▲                    │ observe + update state
   └────────────────────┘
      │ hand-off
      ▼
Evaluator ── continue ──> Executor
          ── replan ────> Replanner (new LLM plan, keeps valid results) ──> Executor
          ── complete ──> Aggregator ──> final response
```

---

## Common Issues

### ModuleNotFoundError

```bash
pip install -r requirements.txt
```

### Missing API Key

Ensure `.env` contains:

```env
GROQ_API_KEY=your_key
```

### Port Already In Use

Run on another port:

```bash
uvicorn main:app --reload --port 8001
```

---

## Stop Server

Press:

```bash
CTRL + C
```
