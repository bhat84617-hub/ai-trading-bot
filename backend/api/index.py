# Bug fix: this file is what Vercel actually runs (see vercel.json), and it
# never included the real API router — only /api/health and / existed here.
# Every REST call from the frontend (auth, watchlist, signals, trades,
# dashboard, broker switch...) was 404ing in production even though it worked
# locally via run.py, because run.py and this file are two different apps.
#
# IMPORTANT — read before deploying to Vercel:
# Even with the router included, TWO things in this bot fundamentally do not
# work on Vercel serverless functions:
#   1. WebSocket endpoint (/ws/{user_id}) — Vercel Python functions don't keep
#      persistent connections open the way this needs.
#   2. The background scanner (backend/app/workers/scanner_worker.py) — it's
#      an infinite `while True` loop. Serverless functions only run while
#      handling a request, then get frozen/killed. Nothing will run this loop
#      for you automatically on Vercel.
# For a bot that needs to keep scanning and holding WebSocket connections,
# deploy the backend on Railway/Render (a long-running process) instead, and
# run scanner_worker.py as a separate worker process/service there. Vercel is
# fine for the Next.js frontend only.

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ..app.core.config import settings
from ..app.api.routes import router

app = FastAPI(title=settings.APP_NAME, version=settings.VERSION)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(router)

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": settings.VERSION, "message": "AI Trading Bot is running on Vercel"}

@app.get("/")
async def root():
    return {"app": settings.APP_NAME, "status": "running on Vercel 🚀"}
