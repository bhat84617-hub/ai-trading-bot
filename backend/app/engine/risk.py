"""
RISK ENGINE
============
Enforces all mandatory risk controls:
1. Position sizing from risk % and stop-loss distance (never flat shares)
2. Mandatory stop-loss on every order (no naked entries EVER)
3. Daily loss limit check (auto-activates kill switch on breach)
4. Kill switch check before every order
5. Max open positions check
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from app.database import get_supabase

logger = logging.getLogger(__name__)


@dataclass
class RiskCheck:
    """Result of a risk check."""
    allowed: bool
    reason: str = ""
    position_size: float = 0.0
    stop_loss_price: float = 0.0
    take_profit_price: float = 0.0


def check_kill_switch() -> tuple[bool, str]:
    """
    Check if kill switch is active.
    Returns (is_active, reason).
    """
    db = get_supabase()
    result = db.table("system_state").select("*").limit(1).execute()
    if result.data:
        state = result.data[0]
        if state.get("kill_switch_active", False):
            return True, state.get("kill_switch_reason", "Kill switch active")
    return False, ""


def check_daily_loss_limit(equity: float) -> tuple[bool, float]:
    """
    Check if daily loss limit has been breached.
    Returns (is_breached, current_daily_loss_pct).
    """
    db = get_supabase()

    # Get risk config
    risk_result = db.table("risk_config").select("*").limit(1).execute()
    if not risk_result.data:
        return False, 0.0
    daily_limit = float(risk_result.data[0].get("daily_loss_limit_pct", 3.0))

    # Get today's starting equity from snapshots
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).isoformat()

    snapshot_result = (
        db.table("account_snapshots")
        .select("equity")
        .gte("snapshot_at", today_start)
        .order("snapshot_at", desc=False)
        .limit(1)
        .execute()
    )

    if snapshot_result.data:
        start_equity = float(snapshot_result.data[0]["equity"])
    else:
        start_equity = equity  # no snapshot yet, use current

    if start_equity <= 0:
        return False, 0.0

    daily_loss_pct = ((start_equity - equity) / start_equity) * 100

    if daily_loss_pct >= daily_limit:
        # Auto-activate kill switch
        _auto_kill_switch(
            f"Daily loss limit breached: {daily_loss_pct:.2f}% >= {daily_limit:.1f}%"
        )
        return True, daily_loss_pct

    return False, daily_loss_pct


def check_max_positions() -> tuple[bool, int]:
    """
    Check if max open positions limit is reached.
    Returns (is_at_max, current_count).
    """
    db = get_supabase()

    risk_result = db.table("risk_config").select("max_open_positions").limit(1).execute()
    max_pos = int(risk_result.data[0]["max_open_positions"]) if risk_result.data else 5

    open_trades = (
        db.table("trade_history")
        .select("id", count="exact")
        .eq("status", "open")
        .execute()
    )
    current_count = open_trades.count or 0

    return current_count >= max_pos, current_count


def check_live_eligibility(symbol: str) -> tuple[bool, str]:
    """
    Check if a symbol has passed walk-forward validation.
    Returns (is_eligible, reason).
    """
    db = get_supabase()

    config_result = (
        db.table("strategy_config")
        .select("live_eligible")
        .eq("symbol", symbol)
        .limit(1)
        .execute()
    )

    if not config_result.data:
        return False, f"No strategy config found for {symbol}"

    if not config_result.data[0].get("live_eligible", False):
        return False, (
            f"{symbol} has not passed walk-forward validation. "
            "Run validation first with minimum 50 trades and profit factor >= 1.2."
        )

    return True, "Validated"


def check_live_armed() -> tuple[bool, str]:
    """
    Check if live trading is currently armed (not expired).
    Returns (is_armed, reason).
    """
    db = get_supabase()
    result = db.table("system_state").select("*").limit(1).execute()

    if not result.data:
        return False, "No system state found"

    state = result.data[0]

    if state.get("trading_mode") != "live":
        return True, "Paper mode — no arming required"

    armed_until = state.get("live_armed_until")
    if not armed_until:
        return False, "Live mode not armed — arm live trading first"

    armed_dt = datetime.fromisoformat(armed_until.replace("Z", "+00:00"))
    if armed_dt < datetime.now(timezone.utc):
        return False, (
            f"Live arming expired at {armed_dt.isoformat()}. "
            "Re-arm live trading to continue."
        )

    return True, f"Armed until {armed_dt.isoformat()}"


def calculate_position_size(
    equity: float,
    risk_pct: float,
    entry_price: float,
    stop_loss_price: float,
) -> float:
    """
    Calculate position size from account risk % and stop-loss distance.
    NEVER a flat share/contract count.

    Formula: position_size = (equity * risk_pct/100) / abs(entry_price - stop_loss_price)
    """
    risk_amount = equity * (risk_pct / 100)
    stop_distance = abs(entry_price - stop_loss_price)

    if stop_distance <= 0:
        logger.warning("Stop distance is zero or negative — cannot size position")
        return 0.0

    size = risk_amount / stop_distance
    return round(size, 6)


def calculate_stop_loss(
    entry_price: float,
    atr: float,
    side: str,
    multiplier: float = 2.0,
) -> float:
    """
    Calculate stop-loss price based on ATR.
    Buy: stop = entry - (ATR * multiplier)
    Sell: stop = entry + (ATR * multiplier)
    """
    if side == "buy":
        return round(entry_price - (atr * multiplier), 2)
    else:
        return round(entry_price + (atr * multiplier), 2)


def calculate_take_profit(
    entry_price: float,
    atr: float,
    side: str,
    multiplier: float = 3.0,
) -> float:
    """
    Calculate take-profit price based on ATR (risk-reward ratio).
    Buy: tp = entry + (ATR * multiplier)
    Sell: tp = entry - (ATR * multiplier)
    """
    if side == "buy":
        return round(entry_price + (atr * multiplier), 2)
    else:
        return round(entry_price - (atr * multiplier), 2)


def full_risk_check(
    symbol: str,
    side: str,
    entry_price: float,
    atr: float,
    equity: float,
    trading_mode: str,
) -> RiskCheck:
    """
    Complete pre-order risk validation.
    Checks in order:
    1. Kill switch
    2. Daily loss limit
    3. Max open positions
    4. Live eligibility (if mode == 'live')
    5. Live arming (if mode == 'live')
    6. Calculate position size
    """
    # 1. Kill switch
    ks_active, ks_reason = check_kill_switch()
    if ks_active:
        return RiskCheck(allowed=False, reason=f"Kill switch active: {ks_reason}")

    # 2. Daily loss limit
    dl_breached, dl_pct = check_daily_loss_limit(equity)
    if dl_breached:
        return RiskCheck(
            allowed=False,
            reason=f"Daily loss limit breached: {dl_pct:.2f}%",
        )

    # 3. Max positions
    at_max, pos_count = check_max_positions()
    if at_max:
        return RiskCheck(
            allowed=False,
            reason=f"Max open positions reached: {pos_count}",
        )

    # 4 & 5. Live mode checks
    if trading_mode == "live":
        eligible, elig_reason = check_live_eligibility(symbol)
        if not eligible:
            return RiskCheck(allowed=False, reason=elig_reason)

        armed, arm_reason = check_live_armed()
        if not armed:
            return RiskCheck(allowed=False, reason=arm_reason)

    # 6. Calculate position size
    db = get_supabase()
    risk_result = db.table("risk_config").select("risk_pct_per_trade").limit(1).execute()
    risk_pct = float(risk_result.data[0]["risk_pct_per_trade"]) if risk_result.data else 1.0

    stop_loss_price = calculate_stop_loss(entry_price, atr, side)
    take_profit_price = calculate_take_profit(entry_price, atr, side)
    position_size = calculate_position_size(equity, risk_pct, entry_price, stop_loss_price)

    if position_size <= 0:
        return RiskCheck(
            allowed=False,
            reason="Position size calculated as zero — check stop-loss distance",
        )

    return RiskCheck(
        allowed=True,
        reason="All risk checks passed",
        position_size=position_size,
        stop_loss_price=stop_loss_price,
        take_profit_price=take_profit_price,
    )


def _auto_kill_switch(reason: str):
    """Automatically activate kill switch on risk breach."""
    try:
        db = get_supabase()
        db.table("system_state").update({
            "kill_switch_active": True,
            "kill_switch_reason": reason,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).neq("id", "impossible").execute()
        logger.critical(f"AUTO KILL SWITCH ACTIVATED: {reason}")
    except Exception as e:
        logger.error(f"Failed to auto-activate kill switch: {e}")
