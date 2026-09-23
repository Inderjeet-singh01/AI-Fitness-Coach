# FitForge AI Chatbot Frontend

Professional React/Vite chat UI for the FitForge AI FastAPI backend.

## Run locally

```bash
npm install
npm run dev
```

Set the backend URL in `.env`:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

For Netlify, set the same variable to your public HTTPS API base, then rebuild.

## UI behavior

- Left sidebar navigation: Chat, My Plan, Profile, Settings (collapses to a drawer on mobile).
- Chat streams live agent activity ("Understanding your goal", "Creating your diet plan", …) driven directly by the backend's SSE phase events, then replaces it with a formatted final report.
- My Plan reads the session's latest calculated/generated data (`GET /sessions/{id}/state`) so results persist outside the chat log.
- Profile edits call the existing `PATCH /sessions/{id}/profile` endpoint.
- Theme supports Light / Dark / System, set in Settings or the top bar.
