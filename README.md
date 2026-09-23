# 🏋️ AI Fitness Coach

> **An AI-powered personalized fitness planning system built with FastAPI, LangGraph, LangChain, Groq, and React.**

[![Live Demo](https://img.shields.io/badge/Live-Demo-00C853?style=for-the-badge)](https://ai-fitness-coach-01.netlify.app/)

[![API Docs](https://img.shields.io/badge/API-Docs-46E3B7?style=for-the-badge)](https://ai-fitness-coach-api-6b9h.onrender.com/docs)

## 🌐 Live Application

Try it here: **https://ai-fitness-coach-01.netlify.app/**

Enter your profile and a fitness question, and the backend orchestrates specialized AI and calculation workflows to generate a structured fitness response.

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

The frontend creates a session once, keeps the profile in it via `PATCH`, and sends each chat message to:

```http
POST /api/v1/sessions/{session_id}/chat/stream
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

| Layer                 | Technology               |
| --------------------- | ------------------------ |
| Frontend              | React                    |
| Frontend Build Tool   | Vite                     |
| Backend               | FastAPI                  |
| Language              | Python                   |
| AI Orchestration      | LangGraph                |
| LLM Framework         | LangChain                |
| LLM Provider          | Groq                     |
| LLM                   | Llama-family model       |
| API Validation        | Pydantic                 |
| Streaming             | Server-Sent Events (SSE) |
| Deployment - Frontend | Netlify                  |
| Deployment - Backend  | Render                   |
| Version Control       | Git + GitHub             |

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
│   ├── agents/          # Planner and aggregator agent logic
│   ├── api/             # FastAPI routes
│   ├── config/          # Settings (reads .env)
│   ├── graph/           # LangGraph workflow + state
│   ├── memory/          # Session memory
│   ├── models/          # Data models
│   ├── schemas/         # Pydantic request/response schemas
│   ├── tools/           # Fitness tools/workers (diet, workout, gym, macro, general)
│   ├── tests/
│   ├── main.py          # FastAPI app entrypoint
│   └── requirements.txt
│
├── .env.example
├── .gitignore
└── README.md
```

> File names can evolve as the project is maintained; the important separation is between the React client, FastAPI API layer, graph orchestration, schemas, and fitness tools.

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

## Sessions and Chat

```http
POST   /api/v1/sessions                              # create session (optional initial profile)
PATCH  /api/v1/sessions/{session_id}/profile         # merge profile fields
POST   /api/v1/sessions/{session_id}/chat/stream     # chat turn (SSE), body: {"message": "..."}
GET    /api/v1/sessions/{session_id}/state           # runtime state (debug)
DELETE /api/v1/sessions/{session_id}                 # clear session
GET    /health
```

### Request

Create a session (profile is optional and can be completed later with `PATCH .../profile`):

```json
{
  "profile": {
    "weight_kg": 75,
    "height_cm": 175,
    "gender": "male",
    "age": 25,
    "activity_level": "moderately_active",
    "location": "India"
  }
}
```

Then chat with only the message:

```json
{ "message": "How many calories and protein should I consume?" }
```

### Response

The endpoint uses **Server-Sent Events (SSE)**.

The stream can contain AI response chunks and ends with a final `done` event containing this turn's structured fitness data, the final report, and a `status` of `success`, `needs_input`, `incomplete` or `error` (`success` only when the evaluator confirmed the goal was met).

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

Create your `.env` file from the provided template (run from the project root):

```bash
cp .env.example .env
```

Then open `.env` and fill in your own values — see [Environment Variables](#-environment-variables) below.

Run FastAPI:

```bash
uvicorn main:app --reload
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

Never commit real API keys to GitHub. `.env` files are already excluded via `.gitignore`; only the `.env.example` templates are tracked.

## Backend (`.env` in the project root)

Copy [`.env.example`](.env.example) to `.env` and fill in your own values:

```bash
cp .env.example .env
```

| Variable                    | Required | Description                                                                                        |
| --------------------------- | -------- | -------------------------------------------------------------------------------------------------- |
| `GROQ_API_KEY`              | ✅       | API key for Groq LLM inference. Get one at [console.groq.com/keys](https://console.groq.com/keys). |
| `GROQ_MODEL`                | Optional | Main Groq model used for AI worker responses. Defaults to `openai/gpt-oss-120b`.                   |
| `GROQ_ROUTER_MODEL`         | Optional | Lighter Groq model used for planning/routing. Defaults to `openai/gpt-oss-20b`.                    |
| `SERPER_API_KEY`            | Optional | Powers location search for the gym-finder tool. Get one at [serper.dev](https://serper.dev/).      |
| `GEOAPIFY_API_KEY`          | Optional | Powers geocoding for the gym-finder tool. Get one at [geoapify.com](https://www.geoapify.com/).    |
| `MAX_OUTPUT_TOKENS`         | Optional | Output token cap for AI workers. Defaults to `700`.                                                |
| `ROUTER_MAX_OUTPUT_TOKENS`  | Optional | Output token cap for the planner/router. Defaults to `700`.                                        |
| `GENERAL_MAX_OUTPUT_TOKENS` | Optional | Output token cap for the general-assistant worker. Defaults to `450`.                              |
| `GYM_MAX_OUTPUT_TOKENS`     | Optional | Output token cap for the gym-finder worker. Defaults to `450`.                                     |
| `TEMPERATURE`               | Optional | LLM sampling temperature. Defaults to `0.2`.                                                       |
| `MAX_REPLANS`               | Optional | Max replan cycles per chat turn. Defaults to `3`.                                                  |
| `MAX_EXECUTION_STEPS`       | Optional | Max executor steps per chat turn. Defaults to `20`.                                                |

`GEOAPIFY_API_KEY` and `SERPER_API_KEY` are only needed if you want the gym-finder tool's location search to work; the rest of the app runs fine without them.

## Frontend (`frontend/.env`)

Copy [`frontend/.env.example`](frontend/.env.example) to `frontend/.env`:

```bash
cd frontend
cp .env.example .env
```

| Variable            | Required | Description                                                      |
| ------------------- | -------- | ---------------------------------------------------------------- |
| `VITE_API_BASE_URL` | ✅       | Base URL of the FastAPI backend, including the `/api/v1` prefix. |

Local development:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

Production (e.g. Netlify):

```env
VITE_API_BASE_URL=https://ai-fitness-coach-api-6b9h.onrender.com/api/v1
```

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
