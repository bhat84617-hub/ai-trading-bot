-- AlgoTrade Bot — Initial Database Schema
-- Run this in your Supabase SQL Editor

-- 1. Watchlist
create table if not exists watchlist (
  id uuid primary key default gen_random_uuid(),
  symbol text not null unique,
  asset_type text not null check (asset_type in ('stock', 'crypto')),
  active boolean default true,
  created_at timestamptz default now()
);

-- 2. Strategy Config (per symbol)
create table if not exists strategy_config (
  id uuid primary key default gen_random_uuid(),
  symbol text references watchlist(symbol) on delete cascade,
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

-- 3. Risk Config (single row)
create table if not exists risk_config (
  id uuid primary key default gen_random_uuid(),
  risk_pct_per_trade numeric default 1.0,
  daily_loss_limit_pct numeric default 3.0,
  max_open_positions int default 5,
  updated_at timestamptz default now()
);

-- 4. System State (single row)
create table if not exists system_state (
  id uuid primary key default gen_random_uuid(),
  kill_switch_active boolean default false,
  kill_switch_reason text,
  trading_mode text default 'paper' check (trading_mode in ('paper', 'live')),
  live_armed_until timestamptz,
  updated_at timestamptz default now()
);

-- 5. Trade History
create table if not exists trade_history (
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

-- 6. Account Snapshots
create table if not exists account_snapshots (
  id uuid primary key default gen_random_uuid(),
  equity numeric,
  buying_power numeric,
  daily_pnl numeric,
  snapshot_at timestamptz default now()
);

-- 7. Backtest Results
create table if not exists backtest_results (
  id uuid primary key default gen_random_uuid(),
  symbol text not null,
  strategy_config_id uuid references strategy_config(id) on delete cascade,
  period_start date,
  period_end date,
  total_trades int,
  win_rate numeric,
  avg_r_multiple numeric,
  profit_factor numeric,
  max_drawdown_pct numeric,
  created_at timestamptz default now()
);

-- 8. Walk-Forward Results
create table if not exists walk_forward_results (
  id uuid primary key default gen_random_uuid(),
  symbol text not null,
  strategy_config_id uuid references strategy_config(id) on delete cascade,
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

-- ============================================================
-- SEED DATA
-- ============================================================

-- Default risk config
insert into risk_config (risk_pct_per_trade, daily_loss_limit_pct, max_open_positions)
values (1.0, 3.0, 5)
on conflict do nothing;

-- Default system state: paper mode, kill switch off
insert into system_state (kill_switch_active, kill_switch_reason, trading_mode, live_armed_until)
values (false, null, 'paper', null)
on conflict do nothing;
