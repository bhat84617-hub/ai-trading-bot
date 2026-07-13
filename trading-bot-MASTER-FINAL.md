# MASTER BUILD PROMPT + PRD/TRD
## Personal Algo Trading Bot Platform — Final Handoff Document (v3.0)

> **Instructions for the AI reading this document:** Build this system exactly as
> specified below. Do not add features not listed. Do not skip the risk/validation
> gates — they are mandatory, not optional suggestions. Where a decision was
> deliberately made to keep scope limited, that constraint is intentional; do not
> "improve" past it without being asked.

---

## MASTER PROMPT (paste this to the build AI as the primary instruction)

```
Build a personal-use algorithmic trading platform with the following non-negotiable
principles:

1. This system executes rule-based technical analysis and risk-managed trade
   execution. It does NOT guarantee profit or any win rate. Do not write any UI
   copy, comment, or log message that implies guaranteed returns.

2. The system only analyzes and trades symbols present in a user-managed watchlist.
   No market-wide scanning.

3. No trading strategy may be armed for LIVE trading until it has passed
   walk-forward validation with a minimum of 50 trades (paper or backtest,
   aggregatable) and a minimum profit factor threshold. This gate is enforced
   in the execution engine's code path, not just shown as a UI warning.

4. Validation eligibility (`live_eligible`) is tracked per symbol + strategy
   config individually. A validated symbol does NOT unlock trading for a newly
   added, unvalidated symbol.

5. Every trade must have a stop-loss attached at order placement. No naked
   entries, ever.

6. Position sizing is calculated from account risk % and stop-loss distance —
   never a flat share/contract count.

7. A kill switch (manual + automatic on daily-loss-limit breach) must halt all
   new order placement instantly, checked before every single order.

8. The system starts in PAPER mode by default. Switching to LIVE requires an
   explicit, separate manual confirmation step, and live authorization
   auto-expires after a set number of hours (must be re-armed).

9. Build with two broker adapters behind a shared interface: Alpaca (US stocks)
   and Bybit (crypto). Do not build a generic "any broker" plugin system.

10. Signal generation requires at least 2 of the following indicators to agree
    before firing a signal: RSI, MACD, moving-average crossover, volume spike.
    Apply a regime filter (e.g. ADX-based trending vs ranging detection) so
    trend-following rules only fire in trending regimes and mean-reversion
    rules only fire in ranging regimes.

11. Build a backtesting engine and a walk-forward validation engine that reuse
    the exact same signal-generation code module as the live/paper engine —
    do not duplicate indicator logic in two places.

12. Every accuracy/win-rate/profit-factor figure shown anywhere in the UI must
    be displayed next to its sample size (trade count). Never show a
    percentage without the count it's based on.

13. Do not add any ML/prediction model in this version — rule-based indicators
    only.

14. Build the dashboard as an asymmetric bento-grid layout (reference image
    provided separately): white rounded cards, soft shadows, one accent color
    for buy/sell states, consistent padding, bold sans-serif headers. See
    Section 7 of the TRD below for exact card composition.

Build in the order specified in Section 9 (Build Order) of the attached TRD.
Stop and ask before adding anything beyond this scope.
```

---

# PART 1 — PRODUCT REQUIREMENTS DOCUMENT (PRD)

## 1. Purpose
A personal-use algorithmic trading system that monitors a user-defined watchlist,
runs rule-based technical analysis with multi-indicator confirmation and regime
awareness, validates every strategy through backtesting and walk-forward testing
before allowing live capital, and executes trades within strict risk limits.
Single user, self-hosted, no billing or multi-tenancy.

## 2. Problem Statement
Manual trade monitoring and execution is time-consuming and emotionally biased.
The user wants systematic, rule-based execution restricted to a known set of
symbols, with hard risk controls and evidence-based validation — not a system
that promises profit, which no legitimate system can.

## 3. Goals
- Automate signal generation and order execution for a fixed watchlist
- Require at least 2 confirming indicators + regime awareness before any signal
- Validate every strategy via backtest + walk-forward testing before live capital
  is risked (minimum 50 trades, minimum profit factor)
- Enforce risk limits automatically (position sizing, daily loss cap, stop-loss,
  kill switch)
- Provide a single professional dashboard (bento grid) for account state,
  watchlist, trade history, validation status, and performance
- Support both paper and live trading with a clear, deliberate, auto-expiring
  switch between them
- Keep infrastructure cost near-zero (free-tier broker APIs, free/low-cost hosting)

## 4. Non-Goals
- Not a multi-user SaaS product; not a signal-selling service
- Not a guaranteed-profit system — no feature or copy implies win-rate guarantees
- Not a generic "connect any broker" system — Alpaca (stocks) + Bybit (crypto) only
- Not a fully unattended, indefinitely-live system — live trading auto-expires
  and requires periodic manual re-arming
- Not an ML/predictive system in this version — rule-based indicators only
- Not a sub-minute scalping system in this version — timeframe starts at 5-min
  bars; a streaming/tick-level architecture is a separate, larger rebuild not
  in scope here

## 5. Users
Single user (owner). No roles/permissions beyond a login to protect the dashboard.

## 6. Key User Stories
1. Add/remove watchlist symbols so only those are analyzed.
2. View live signals (buy/sell/hold) with the indicators and regime behind them.
3. See account equity, open positions, and daily P&L at a glance.
4. Review full trade history with entry/exit/P&L per trade.
5. Set risk parameters (risk %, daily loss limit) from the dashboard.
6. Run a backtest for any symbol/strategy and see win rate, profit factor,
   drawdown, and trade count before trusting it.
7. Run walk-forward validation and see a clear pass/fail with the reason
   (e.g. "32/50 trades, needs 18 more").
8. Flip between paper and live mode, with live requiring explicit confirmation
   and auto-expiring.
9. Hit a kill switch that immediately stops all new trade entries.
10. See the system automatically pause new entries if the daily loss limit is hit.

## 7. Feature List (Prioritized)

### P0 (MVP — must have)
- Watchlist management
- Multi-indicator signal engine (RSI, MACD, MA crossover, volume) — fires only
  on 2+ agreement
- Regime detector (trending vs ranging) gating which indicator set applies
- Backtesting engine (shared code with live engine)
- Walk-forward validation engine, writing `live_eligible` per symbol/strategy
- Alpaca broker adapter (paper + live)
- Risk engine: position sizing by %, mandatory stop-loss, daily loss limit
- Kill switch (manual + auto on drawdown)
- Trade execution engine with full logging
- Dashboard: account overview, watchlist, trade history, risk status, backtest panel

### P1 (fast follow)
- Equity curve chart
- Per-symbol performance stats (explicitly labeled historical, not predictive)
- Live-mode arming flow with auto-expiry, gated by `live_eligible`

### P2 (later)
- Bybit adapter for crypto
- Additional indicators / strategy presets
- Notification integration (Telegram/email alerts)

## 8. Success Criteria
- 100% of trades traceable to an active watchlist entry
- Zero trades placed without an attached stop-loss
- Daily loss limit halts new entries within one polling cycle of breach
- No live trade placed for any symbol/strategy without a passing
  `walk_forward_results` row on file
- Every accuracy figure in the UI shows its sample size alongside it

## 9. Risks & Constraints
- Broker API rate limits — polling frequency must respect Alpaca's limits
- Free-tier hosting (cold starts, limited compute) may affect polling reliability
- Backtest quality depends on historical data quality/depth — Alpaca free tier
  has limited history; a secondary data source may be needed for deeper backtests
- Past performance (backtest, paper, or live) never guarantees future results;
  the dashboard should flag when live/paper performance diverges materially
  from backtest expectations
- Validation takes real calendar time (typically 1–4 weeks depending on
  timeframe and number of watchlist symbols) — there is no legitimate shortcut
  that preserves statistical reliability

---

# PART 2 — TECHNICAL REQUIREMENTS DOCUMENT (TRD)

## 1. Tech Stack
- **Backend:** FastAPI (Python 3.11+)
- **Frontend:** Next.js 14 (App Router) + TypeScript + Tailwind CSS
- **Database:** Supabase (Postgres), single-user auth (email/password)
- **Broker APIs:** Alpaca (stocks, REST + WebSocket market data), Bybit (crypto, P2)
- **Hosting:** Backend on Render, Frontend on Vercel, DB on Supabase
- **Scheduler:** APScheduler or Render Cron hitting an internal `/scan` endpoint
  every 5 minutes (default, configurable)

## 2. System Architecture
```
┌─────────────┐      ┌──────────────────┐      ┌─────────────┐
│  Next.js UI │◄────►│   FastAPI Backend │◄────►│   Supabase  │
│  (Vercel)   │ REST │   (Render)        │ SQL  │  (Postgres) │
└─────────────┘      └─────────┬─────────┘      └─────────────┘
                                │
                      ┌─────────┴─────────┐
                      │  Broker Adapters   │
                      │  (Alpaca / Bybit)  │
                      └────────────────────┘
```

## 3. Database Schema (Supabase/Postgres)
```sql
create table watchlist (
  id uuid primary key default gen_random_uuid(),
  symbol text not null unique,
  asset_type text not null check (asset_type in ('stock', 'crypto')),
  active boolean default true,
  created_at timestamptz default now()
);

create table strategy_config (
  id uuid primary key default gen_random_uuid(),
  symbol text references watchlist(symbol),
  rsi_period int default 14,
  rsi_overbought numeric default 70,
  rsi_oversold numeric default 30,
  macd_fast int default 12,
  macd_slow int default 26,
  macd_signal int default 9,
  ma_short int default 20,
  ma_long int default 50,
  live_eligible boolean default false,
  updated_at timestamptz default now()
);

create table risk_config (
  id uuid primary key default gen_random_uuid(),
  risk_pct_per_trade numeric default 1.0,
  daily_loss_limit_pct numeric default 3.0,
  max_open_positions int default 5,
  updated_at timestamptz default now()
);

create table system_state (
  id uuid primary key default gen_random_uuid(),
  kill_switch_active boolean default false,
  kill_switch_reason text,
  trading_mode text default 'paper' check (trading_mode in ('paper', 'live')),
  live_armed_until timestamptz,
  updated_at timestamptz default now()
);

create table trade_history (
  id uuid primary key default gen_random_uuid(),
  symbol text not null,
  side text not null check (side in ('buy', 'sell')),
  entry_price numeric,
  exit_price numeric,
  quantity numeric,
  stop_loss numeric,
  take_profit numeric,
  pnl numeric,
  status text check (status in ('open', 'closed', 'cancelled', 'failed')),
  signal_reason jsonb,
  broker text not null,
  mode text check (mode in ('paper', 'live')),
  opened_at timestamptz default now(),
  closed_at timestamptz
);

create table account_snapshots (
  id uuid primary key default gen_random_uuid(),
  equity numeric,
  buying_power numeric,
  daily_pnl numeric,
  snapshot_at timestamptz default now()
);

create table backtest_results (
  id uuid primary key default gen_random_uuid(),
  symbol text not null,
  strategy_config_id uuid references strategy_config(id),
  period_start date,
  period_end date,
  total_trades int,
  win_rate numeric,
  avg_r_multiple numeric,
  profit_factor numeric,
  max_drawdown_pct numeric,
  created_at timestamptz default now()
);

create table walk_forward_results (
  id uuid primary key default gen_random_uuid(),
  symbol text not null,
  strategy_config_id uuid references strategy_config(id),
  num_windows int,
  total_trades_across_windows int,
  aggregate_win_rate numeric,
  aggregate_profit_factor numeric,
  worst_window_drawdown_pct numeric,
  passed boolean,
  min_trades_threshold int default 50,
  min_profit_factor_threshold numeric default 1.2,
  created_at timestamptz default now()
);
```

## 4. Broker Adapter Interface
```python
class IBrokerAdapter(ABC):
    @abstractmethod
    def get_quote(self, symbol: str) -> Quote: ...
    @abstractmethod
    def get_account(self) -> AccountInfo: ...
    @abstractmethod
    def get_positions(self) -> list[Position]: ...
    @abstractmethod
    def place_order(self, order: OrderRequest) -> OrderResult: ...
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool: ...
```

## 5. Core Engine Flow
```
LIVE/PAPER SCAN CYCLE:
1. Fetch active watchlist symbols
2. For each symbol:
   a. Fetch recent OHLCV data
   b. Detect regime (trending / ranging) via ADX or equivalent
   c. Compute indicators (RSI, MACD, MA crossover, volume)
   d. Apply only the regime-matched indicator set
   e. Fire signal only if 2+ applicable indicators agree
3. For each buy/sell signal:
   a. Skip if kill_switch_active
   b. Skip if daily loss limit breached
   c. Skip if max_open_positions reached
   d. Calculate position size from risk_pct_per_trade + stop-loss distance
   e. If mode == 'live': require live_armed_until > now() AND
      strategy_config.live_eligible == true for this symbol
   f. Place order with stop-loss/take-profit attached
   g. Log to trade_history
4. Update account_snapshots

BACKTEST / WALK-FORWARD (on-demand, shares signal code with live engine):
1. Select symbol + strategy_config + historical period
2. Replay historical bars through the SAME signal-generation module used live
3. Simulate fills/stop-loss/take-profit/position sizing via the same risk engine
4. Store result in backtest_results
5. For walk-forward: repeat across N rolling windows, aggregate into
   walk_forward_results
6. Set live_eligible = true only if:
   - total_trades_across_windows >= min_trades_threshold (default 50)
   - aggregate_profit_factor >= min_profit_factor_threshold (default 1.2)
   - worst_window_drawdown_pct within user-set tolerance
```

## 6. REST API Endpoints
```
GET/POST/DELETE /api/watchlist
GET  /api/account
GET  /api/positions
GET  /api/trades?limit=&symbol=
GET  /api/equity-curve
GET/PUT /api/risk-config
GET  /api/system-state
POST /api/system-state/kill-switch
POST /api/system-state/mode
POST /api/system-state/arm-live
POST /api/scan
POST /api/backtest
POST /api/walk-forward
GET  /api/strategy-config/{symbol}
```

## 7. Frontend Dashboard Spec (Bento Grid, per reference image)
Asymmetric grid of white rounded cards on light neutral background, soft
shadows, one accent color (green/red) for buy/sell states, 16–24px padding,
bold sans-serif headers.

- **Row 1:** Account Overview (spans 2 cols) | Risk Status (1 col)
- **Row 2:** Watchlist + Live Signals (1 col) | Equity Curve (spans 2 cols)
- **Row 3:** Trade History (spans 2 cols) | Per-Symbol Performance (1 col)
- **Row 4:** Backtest/Validation Panel (full width) — form + results table,
  `live_eligible` badge per symbol with pass/fail reason and sample size
- **Persistent header:** mode toggle (paper/live), kill switch button (always
  visible, red when active)

## 8. Environment / Config
```
ALPACA_API_KEY=
ALPACA_SECRET_KEY=
ALPACA_BASE_URL=
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
SCAN_INTERVAL_SECONDS=300
```

## 9. Build Order
1. Supabase schema + seed data
2. FastAPI skeleton + Alpaca adapter + read-only account/positions endpoints
3. Shared signal engine module (indicators + regime detector + confirmation logic)
4. Backtesting engine + `/api/backtest`
5. Walk-forward validation + `/api/walk-forward`, writing `live_eligible`
6. `/api/scan` using the shared signal engine, logging signals only
7. Risk engine wired in, paper mode only
8. Execution engine — paper orders, populate trade_history
9. Dashboard: Account Overview + Watchlist + Trade History
10. Backtest/Validation panel UI
11. Kill switch + risk config UI
12. Equity curve + per-symbol performance cards
13. Live mode arming flow, gated by `live_eligible`
14. Bybit adapter (only after step 13 is stable in paper mode)

## 10. Explicit Constraints for the Build AI
- No ML/prediction model in this version
- No generic multi-broker plugin system — two adapters only
- No order without an attached stop-loss
- Paper mode is the default; live requires explicit, auto-expiring arming
- No live trade without a passing `walk_forward_results` row — enforced in code
- Every accuracy figure shown with its sample size, never in isolation
- Backtest and live signal logic share one code module — no duplication
- No UI copy implying guaranteed profit or win rate
- No sub-minute scalping architecture in this version — 5-min minimum timeframe
