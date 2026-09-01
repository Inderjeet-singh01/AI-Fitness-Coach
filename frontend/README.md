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

- Only the right chat pane scrolls.
- Profile pane remains stable while the conversation grows.
- Streaming text is rendered with a subtle cursor and is replaced by a clean formatted final report.
- Dark/light mode is available in the header.
