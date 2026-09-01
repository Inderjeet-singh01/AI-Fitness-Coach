# main.py
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config.settings import settings
from api.routes import router as api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="Production-grade Agentic AI Multi-Agent Fitness Planner using LangGraph, FastAPI, and Groq."
)

# Configure CORS Middleware for cross-origin frontend interfaces or mobile apps
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust to explicit origins in a hard production environment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Modular API Version 1 Routes
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/", tags=["Root"])
def root_status_check():
    """
    High-speed health check endpoint for deployment monitoring.
    """
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "engine": "LangGraph Orchestrator",
        "llm_provider": "Groq (Llama-3)"
    }

if __name__ == "__main__":
    # Runs the ASGI server programmatically
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)