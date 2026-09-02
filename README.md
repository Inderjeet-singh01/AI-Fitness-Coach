# 🏋️ AI Fitness Coach

> **An AI-powered personalized fitness planning system built with FastAPI, LangGraph, LangChain, Groq, and React.**

[![Live Demo](https://img.shields.io/badge/Live-Demo-00C853?style=for-the-badge)](https://ai-fitness-coach-01.netlify.app/)
[![Backend](https://img.shields.io/badge/API-Render-46E3B7?style=for-the-badge)](https://ai-fitness-coach-api-6b9h.onrender.com/)
[![Frontend](https://img.shields.io/badge/Frontend-React%20%2B%20Vite-61DAFB?style=for-the-badge)](https://react.dev/)
[![Backend](https://img.shields.io/badge/Backend-FastAPI-009688?style=for-the-badge)](https://fastapi.tiangolo.com/)
[![AI](https://img.shields.io/badge/LLM-Groq%20%2F%20Llama-orange?style=for-the-badge)](https://groq.com/)

## 🌐 Live Application

**Try the application:**  
https://ai-fitness-coach-01.netlify.app/

The application provides a personalized fitness planning experience where users enter their profile and fitness requirements, and the backend orchestrates specialized AI and calculation workflows to generate a structured fitness response.

---

## 📌 Overview

AI Fitness Coach is a full-stack Generative AI application designed to provide **personalized fitness and nutrition guidance** from a user's physical profile, activity level, and natural-language query.

Instead of sending every request directly to an LLM, the backend uses **LangGraph orchestration** to route work through specialized components for deterministic fitness calculations and AI-generated recommendations.

The system can calculate and present:

- BMI
- BMR
- TDEE / calorie requirements
- Daily water intake
- Macronutrient targets
- Diet recommendations
- Workout recommendations
- Gym/home fitness guidance
- General fitness assistance

The final response is streamed to the frontend using **Server-Sent Events (SSE)** so users can see the AI response as it is generated.

---

# ✨ Key Features

### 🤖 AI-Powered Fitness Planning
Generates personalized fitness recommendations using a Groq-hosted LLM.

### 🧠 Multi-Agent / Graph-Based Architecture
LangGraph is used to orchestrate a planner and specialized fitness workers rather than relying on one monolithic AI call.

### 📊 Deterministic Fitness Calculations
Core numerical calculations such as BMI, BMR, hydration, calories, and macronutrients are handled through dedicated tools/workers.

This keeps numerical outputs more controlled and reduces unnecessary dependence on LLM-generated arithmetic.

### 💬 Natural-Language Fitness Queries
Users can ask questions such as:

```text
How many calories should I eat per day?

Give me a workout plan for muscle gain.

How much protein should I consume?

What should I eat today?

Suggest a home workout.
```

### ⚡ Real-Time Streaming
The backend exposes a streaming endpoint and sends AI output to the React frontend using SSE.

This improves perceived response time because the user does not have to wait for the entire response before seeing output.

### 📱 Responsive Web Interface
React + Vite frontend designed for a clean interactive fitness-coaching experience.

### 📈 Personalized Metrics Dashboard
The frontend displays key user metrics including:

- BMI
- BMR
- Hydration
- Protein

### ☁️ Production Deployment
The project is deployed using a separated frontend/backend architecture:

```text
React + Vite
      │
      │ HTTPS / SSE
      ▼
Netlify
      │
      │ API requests
      ▼
FastAPI Backend
      │
      ▼
LangGraph Orchestrator
      │
 ┌────┴─────────────────────────┐
 ▼                              ▼
Fitness Tools / Workers       Groq LLM
```

---

# 🏗️ System Architecture

```text
                    ┌──────────────────────┐
                    │      React UI        │
                    │      Vite Frontend   │
                    └──────────┬───────────┘
                               │
                         HTTPS / SSE
                               │
                               ▼
                    ┌──────────────────────┐
                    │     FastAPI API      │
                    │   /api/v1/...        │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ LangGraph Workflow   │
                    │                      │
                    │ Planner / Router     │
                    └──────────┬───────────┘
                               │
             ┌─────────────────┼─────────────────┐
             │                 │                 │
             ▼                 ▼                 ▼
        BMI / BMR          Water / Macro     AI Workers
          Tools               Tools        Diet / Workout
             │                 │                 │
             └─────────────────┼─────────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │     Aggregator       │
                    │ Final Fitness Report │
                    └──────────┬───────────┘
                               │
                               ▼
                         SSE "done" event
                               │
                               ▼
                    ┌──────────────────────┐
                    │     React UI         │
                    │ Final Report + Stats │
                    └──────────────────────┘
```

---

# 🔄 Request Flow

A typical request follows this pipeline:

### 1. User submits profile

The frontend collects information such as:

- Age
- Gender
- Height
- Weight
- Activity level
- Location
- Fitness query

### 2. Frontend calls the backend

```http
POST /api/v1/generate-plan/stream
```

### 3. FastAPI validates the request

The request is validated using Pydantic schemas before entering the AI workflow.

### 4. LangGraph orchestrates the request

The workflow determines which specialized workers are relevant to the user's query.

### 5. Fitness tools calculate numerical values

Examples include:

```text
BMI
BMR
TDEE / calories
Water intake
Protein
Carbohydrates
Fats
```

### 6. AI workers generate recommendations

Depending on the request, specialized workers can handle:

```text
Diet
Workout
Gym
General fitness questions
```

### 7. Aggregator builds the final response

The generated information is combined into a final structured fitness report.

### 8. Backend streams the response

The FastAPI endpoint sends incremental events using SSE.

### 9. React consumes the stream

The frontend parses the events and updates the interface in real time.

---

# 🧩 Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React |
| Frontend Build Tool | Vite |
| Backend | FastAPI |
| Language | Python |
| AI Orchestration | LangGraph |
| LLM Framework | LangChain |
| LLM Provider | Groq |
| LLM | Llama-family model |
| API Validation | Pydantic |
| Streaming | Server-Sent Events (SSE) |
| Deployment - Frontend | Netlify |
| Deployment - Backend | Render |
| Version Control | Git + GitHub |

---

# 📂 Project Structure

```text
AI-Fitness-Coach/
│
├── frontend/
│   ├── src/
│   │   ├── main.jsx
│   │   ├── api.js
│   │   └── ...
│   │
│   ├── package.json
│   ├── vite.config.js
│   └── ...
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── ...
│   │   ├── graph/
│   │   │   └── workflow.py
│   │   ├── tools/
│   │   │   └── ...
│   │   ├── schemas/
│   │   │   └── ...
│   │   ├── services/
│   │   │   └── ...
│   │   └── main.py
│   │
│   ├── requirements.txt
│   └── ...
│
├── .gitignore
└── README.md
```

> File names can evolve as the project is maintained; the important separation is between the React client, FastAPI API layer, graph orchestration, schemas, services, and fitness tools.

---

# 🔌 API

## Health Check

```http
GET /
```

The deployed backend exposes a lightweight health response.

Example:

```json
{
  "status": "healthy",
  "project": "AI Fitness & Nutrition Assistant",
  "engine": "LangGraph Orchestrator",
  "llm_provider": "Groq (Llama-3)"
}
```

## Generate Fitness Plan

```http
POST /api/v1/generate-plan/stream
```

### Request

```json
{
  "session_id": "example-session",
  "weight_kg": 75,
  "height_cm": 175,
  "gender": "male",
  "age": 25,
  "activity_level": "moderately_active",
  "location": "India",
  "query": "How many calories and protein should I consume?"
}
```

### Response

The endpoint uses **Server-Sent Events (SSE)**.

The stream can contain AI response chunks and ends with a final `done` event containing structured fitness data and the final report.

---

# ⚙️ Local Development

## Prerequisites

Install:

- Python 3.10+
- Node.js
- npm
- Git
- Groq API key

---

## 1. Clone the repository

```bash
git clone https://github.com/Inderjeet-singh01/AI-Fitness-Coach.git
cd AI-Fitness-Coach
```

---

# 🐍 Backend Setup

```bash
cd backend
```

Create a virtual environment:

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file:

```env
GROQ_API_KEY=your_groq_api_key
```

Run FastAPI:

```bash
uvicorn app.main:app --reload
```

Backend should be available at:

```text
http://127.0.0.1:8000
```

Swagger documentation:

```text
http://127.0.0.1:8000/docs
```

---

# ⚛️ Frontend Setup

Open another terminal:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Create:

```text
.env
```

Add:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

Run the frontend:

```bash
npm run dev
```

The Vite development server will provide the local frontend URL.

---

# 🔐 Environment Variables

Never commit API keys to GitHub.

Recommended frontend configuration:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

For production:

```env
VITE_API_BASE_URL=https://ai-fitness-coach-api-6b9h.onrender.com/api/v1
```

Backend:

```env
GROQ_API_KEY=your_secret_key
```

Add `.env` to `.gitignore`.

---

# 🚀 Deployment

The production application uses a decoupled deployment architecture.

## Frontend — Netlify

```text
https://ai-fitness-coach-01.netlify.app/
```

Build command:

```bash
npm run build
```

Publish directory:

```text
dist
```

Production environment variable:

```env
VITE_API_BASE_URL=https://ai-fitness-coach-api-6b9h.onrender.com/api/v1
```

## Backend — Render

```text
https://ai-fitness-coach-api-6b9h.onrender.com/
```

The backend serves the FastAPI application and communicates with Groq for LLM-powered responses.

---

# 🧠 Why LangGraph?

A simple chatbot could send every request directly to an LLM.

This project takes a more structured approach.

```text
User Query
    │
    ▼
Planner / Router
    │
    ├── BMI / BMR
    ├── Water
    ├── Macro
    ├── Diet
    ├── Workout
    ├── Gym
    └── General
    │
    ▼
Aggregator
    │
    ▼
Final Response
```

This architecture provides:

- Modular AI workflows
- Specialized responsibilities
- Better separation between calculations and generation
- Easier debugging
- Easier extension of new fitness capabilities
- A clear path toward more complex agentic workflows

---

# ⚡ Why Streaming?

The application uses **Server-Sent Events** for the fitness-plan endpoint.

Without streaming:

```text
Request → Wait → Complete AI response → Display
```

With streaming:

```text
Request
   ↓
AI starts generating
   ↓
Chunk 1 → UI
Chunk 2 → UI
Chunk 3 → UI
...
Final result → UI
```

This improves perceived responsiveness and provides a more natural conversational experience.

---

# 📊 Engineering Highlights

From an engineering perspective, this project demonstrates experience with:

### Backend Engineering

- REST API development with FastAPI
- Pydantic request validation
- Async request handling
- Streaming responses
- CORS configuration
- Modular backend architecture

### Generative AI

- LLM integration using Groq
- LangChain
- LangGraph
- Prompt-based AI workers
- Agent/workflow orchestration
- Structured AI responses

### AI System Design

- Planner-based routing
- Specialized workers
- Deterministic calculation tools
- Aggregation layer
- Separation of AI generation from numerical calculations

### Frontend

- React
- Vite
- API integration
- SSE stream parsing
- Dynamic dashboard updates
- Environment-based API configuration

### Deployment

- Git/GitHub
- Netlify
- Render
- Production environment variables
- Separate frontend/backend deployment

---

# 🧪 Example Use Cases

### Nutrition

```text
"How many calories should I eat to lose weight?"
```

### Protein

```text
"How much protein do I need per day?"
```

### Workout

```text
"Create a workout plan for muscle gain."
```

### Home Training

```text
"Give me a workout I can do at home without equipment."
```

### Fitness Metrics

```text
"Calculate my BMI and BMR."
```

---

# 🛡️ Disclaimer

This application is intended for **educational and informational purposes**.

AI-generated fitness and nutrition recommendations should not be treated as medical advice. Users with medical conditions, injuries, or specific health concerns should consult a qualified healthcare professional before changing their diet or exercise routine.

---

# 🔮 Future Improvements

Potential future development areas include:

- Persistent user profiles
- Authentication and authorization
- Workout history and progress tracking
- Database-backed user data
- Automated fitness progress analytics
- More specialized fitness agents
- Automated testing and evaluation pipelines
- Observability and production monitoring
- Rate limiting and abuse protection
- Improved recommendation evaluation
- Mobile application

---

# 👨‍💻 Author

**Inderjeet Singh**

Machine Learning Engineer | GenAI Engineer

- GitHub: https://github.com/Inderjeet-singh01
- LinkedIn: https://www.linkedin.com/in/inderjeetsingh0101/
- Portfolio: https://inderjeet-resume.netlify.app/

---

# ⭐ Project

If you find this project interesting, feel free to **star the repository** and explore the implementation.

**Live Demo:**  
https://ai-fitness-coach-01.netlify.app/

**Backend API:**  
https://ai-fitness-coach-api-6b9h.onrender.com/

---

## 📄 License

Add the license that matches the repository's intended distribution before publishing. If this project is not intended to be open source, consider keeping the repository private or explicitly documenting the permitted use.
