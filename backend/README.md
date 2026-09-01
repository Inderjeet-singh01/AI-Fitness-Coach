# FitForge AI Backend — Cost-Controlled Streaming

FastAPI + LangGraph + Groq backend for the FitForge AI chatbot.

## What changed

- SSE streaming endpoint: `POST /api/v1/generate-plan/stream`
- Output-token caps for every LLM call.
- `openai/gpt-oss-20b` for routing, general chat, and gym presentation.
- `openai/gpt-oss-120b` for diet/workout generation.
- `max_retries=2` on Groq calls for transient/rate-limit failures.
- Compact recent chat history to reduce input TPM.
- Removed the extra LLM supervisor/audit call from the normal execution path. This materially reduces LLM calls and avoids retry amplification.
- Deterministic aggregator; no extra LLM call for formatting.
- Worker prompts request clean Markdown rather than dense text.

## Environment

Copy `.env.example` to `.env` and add your secrets. Never commit `.env`.

## Run

```bash
python -m uvicorn main:app --reload
```

Swagger: `http://127.0.0.1:8000/docs`

## Cost/throughput notes

For a full report, the graph can still call the planner plus only the selected generative workers. BMI, water, and macro calculations are deterministic. The supervisor LLM was removed from the normal path, so it no longer consumes tokens or causes extra retries.

`MAX_OUTPUT_TOKENS` is a hard upper bound for 120B generation calls. Lower it further if your product does not need long plans.

Streaming improves perceived latency but does not reduce token consumption by itself.
