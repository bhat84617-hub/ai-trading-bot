# AlgoTrade Bot Platform (v3.0)

A personal-use algorithmic trading platform that monitors a user-defined watchlist, runs rule-based technical analysis with multi-indicator confirmation and regime awareness, validates strategies through backtesting/walk-forward testing, and executes trades within strict risk limits.

## Key Features

1. **Rule-Based Engine**: Computes RSI, MACD, MA Crossover, and Volume Spike. ADX regime detector determines trending vs. ranging markets. Fires entry signals only when at least 2 indicators agree.
2. **Mandatory Safety Gates**:
   - **Stop-Loss Enforcement**: Every order placed is paired with a bracket stop-loss order on entry. No naked entries allowed.
   - **Daily Loss Limit**: Halts all new orders if daily equity falls below the configured threshold, auto-triggering the global kill switch.
   - **Kill Switch**: Global master halt option, checked before placing any order.
   - **Validation Gate**: Live execution is strictly restricted to symbols that have passed walk-forward validation (minimum 50 trades, minimum 1.2 profit factor).
3. **Paper & Live Arming**: Starts in paper trading mode by default. Switching to Live requires explicit arming which automatically expires after a selected number of hours.
4. **Bento-Grid Dashboard**: Asymmetric bento-grid card layout displaying account parameters, active watchlist, equity curve performance, trade log history, and walk-forward verification outputs.

---

## Getting Started

### 1. Prerequisites
- **Node.js** (v18+) & **NPM** (v10+)
- **Python** (v3.11+)
- **Alpaca** API credentials (free paper trading account works)
- **Supabase** account (free tier PostgreSQL database)

### 2. Database Setup (Supabase)
1. Go to [Supabase](https://supabase.com) and create a new project.
2. Navigate to the SQL Editor and copy-paste the contents of the database schema file:
   `backend/migrations/001_initial_schema.sql`
3. Execute the SQL statements to initialize the database tables and seed configurations.

### 3. Backend Setup
1. Open a terminal, navigate to the `backend` folder:
   ```bash
   cd backend
   ```
2. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
3. Open `.env` and fill in your Supabase connection info and Alpaca API credentials.
4. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. Start the FastAPI backend:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
   The backend API will run at `http://localhost:8000`.

### 4. Frontend Setup
1. Open a new terminal, navigate to the `frontend` folder:
   ```bash
   cd frontend
   ```
2. Install npm dependencies:
   ```bash
   npm install
   ```
3. Start the Next.js development server:
   ```bash
   npm run dev
   ```
   The interactive dashboard will open at `http://localhost:3000`.
