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

### Endpoint

```http
POST /generate-plan
```

### Request Body

```json
{
  "age": 25,
  "gender": "male",
  "weight": 80,
  "height": 176,
  "goal": "fat loss",
  "activity_level": "moderately_active",
  "query": "Create a complete fat loss plan"
}
```

---

## 8. Expected Flow

```text
User Request
      │
      ▼
Planner Agent
      │
      ▼
Tool Selection
      │
      ├── BMI Tool
      ├── Water Tool
      ├── Macro Tool
      ├── Diet Generator
      ├── Workout Generator
      └── Gym Finder
      │
      ▼
Supervisor Agent
      │
      ▼
Aggregator Agent
      │
      ▼
Final Fitness Report
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
