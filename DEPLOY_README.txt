🤖 AI Trading Bot — Deployment Package
========================================

INCLUDED FOLDERS:
  backend/    → Python FastAPI backend (deploy this)
  frontend/   → Next.js dashboard (deploy this)
  docker/     → Docker Compose files

SETUP GUIDE: See "bot/docs/SETUP_GUIDE.html" or "bot/docs/SETUP_GUIDE.md"

QUICK START:
  1. cd backend && pip install -r requirements.txt
  2. cp .env.example .env (fill in your API keys)
  3. python run.py
  4. cd frontend && npm install && npm run dev
  5. Open http://localhost:3000

FOR FULL SETUP: Read bot/docs/SETUP_GUIDE.md
