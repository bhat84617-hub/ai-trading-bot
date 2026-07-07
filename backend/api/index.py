from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ..app.core.config import settings

app = FastAPI(title=settings.APP_NAME, version=settings.VERSION)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": settings.VERSION, "message": "AI Trading Bot is running on Vercel"}

@app.get("/")
async def root():
    return {"app": settings.APP_NAME, "status": "running on Vercel 🚀"}
