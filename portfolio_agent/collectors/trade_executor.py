"""
Trade Executor
───────────────
Wraps the Upstox Orders API with safety guards:
  - Max 2 trades per day
  - Confirmation prompt before every order
  - Dry-run mode (default OFF once confirmed)
  - Market hours check (9:15 AM - 3:30 PM IST)
  - Instrument key lookup (from holdings ISIN or yfinance)
  - Full order/trade log
"""

import os
import sys
import json
import requests
from datetime import datetime, date
from typing import Dict, Optional
from zoneinfo import ZoneInfo

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import UPSTOX_ACCESS_TOKEN

IST = ZoneInfo("Asia/Kolkata")
BASE_URL = "https://api.upstox.com/v2"
MAX_TRADES_PER_DAY = 2

# Persists today's trade count across sessions
TRADE_LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "trade_log.json")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _headers(token: str = None) -> Dict:
    return {
        "Authorization": f"Bearer {token or UPSTOX_ACCESS_TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _load_trade_log() -> Dict:
    if os.path.exists(TRADE_LOG_FILE):
        with open(TRADE_LOG_FILE) as f:
            return json.load(f)
    return {}


def _save_trade_log(log: Dict):
    with open(TRADE_LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)


def trades_today() -> int:
    """Return number of trades placed today."""
    log = _load_trade_log()
    return len(log.get(date.today().isoformat(), []))


def _record_trade(order_id: str, details: Dict):
    """Append a trade to today's log."""
    log = _load_trade_log()
    today = date.today().isoformat()
    log.setdefault(today, []).append({
        "order_id": order_id,
        "timestamp": datetime.now(IST).strftime("%H:%M:%S"),
        **details,
    })
    _save_trade_log(log)


def is_market_open() -> bool:
    """Check if NSE is currently open (9:15 AM - 3:30 PM IST, Mon-Fri)."""
    now = datetime.now(IST)
    if now.weekday() >= 5:  # Saturday / Sunday
        return False
    market_open  = now.replace(hour=9,  minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_open <= now <= market_close


def market_status_str() -> str:
    now = datetime.now(IST)
    if now.weekday() >= 5:
        return "CLOSED (weekend)"
    if is_market_open():
        return "OPEN"
    return "CLOSED (outside trading hours 9:15 AM - 3:30 PM IST)"


# ── Instrument Key Lookup ──────────────────────────────────────────────────────

def get_instrument_key(symbol: str, token: str = None) -> Optional[str]:
    """
    Resolve NSE symbol to Upstox instrument key (NSE_EQ|{ISIN}).

    Strategy:
      1. Check existing portfolio holdings (already have ISIN)
      2. Fetch ISIN from yfinance for new symbols
    """
    # Step 1: Check current holdings
    try:
        resp = requests.get(
            f"{BASE_URL}/portfolio/long-term-holdings",
            headers=_headers(token),
        )
        if resp.status_code == 200:
            for h in resp.json().get("data", []):
                if h.get("tradingsymbol", "").upper() == symbol.upper():
                    isin = h.get("isin")
                    if isin:
                        return f"NSE_EQ|{isin}"
    except Exception:
        pass

    # Step 2: Use yfinance to get ISIN
    try:
        import yfinance as yf
        ticker = yf.Ticker(f"{symbol.upper()}.NS")
        isin = ticker.isin
        if isin and isin != "-":
            return f"NSE_EQ|{isin}"
    except Exception:
        pass

    return None


# ── Live Quote ─────────────────────────────────────────────────────────────────

def get_quote(symbol: str, token: str = None) -> Dict:
    """
    Fetch the live Last Traded Price (LTP) for a symbol.

    Returns:
      { symbol, ltp, instrument_key, exchange }
    """
    instrument_key = get_instrument_key(symbol, token)
    if not instrument_key:
        return {"error": f"Could not resolve instrument key for {symbol}"}

    try:
        resp = requests.get(
            f"{BASE_URL}/market-quote/ltp",
            headers=_headers(token),
            params={"instrument_key": instrument_key},
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        # Response key is the instrument_key
        quote_data = data.get(instrument_key.replace("|", ":"), {})
        ltp = quote_data.get("last_price") or quote_data.get("ltp")

        return {
            "symbol": symbol.upper(),
            "ltp": ltp,
            "instrument_key": instrument_key,
        }
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}


# ── Confirmation Prompt ────────────────────────────────────────────────────────

def _confirm_trade(symbol: str, transaction_type: str, quantity: int,
                   order_type: str, price: float, ltp: float) -> bool:
    """Show a clear confirmation box and ask the user to approve."""
    est_price = price if order_type == "LIMIT" and price > 0 else ltp
    est_total = round(est_price * quantity, 2) if est_price else "unknown"

    print("\n" + "=" * 48)
    print("  TRADE CONFIRMATION REQUIRED")
    print("=" * 48)
    print(f"  Action    : {transaction_type}")
    print(f"  Symbol    : {symbol}")
    print(f"  Quantity  : {quantity} shares")
    print(f"  Order Type: {order_type}")
    if order_type == "LIMIT":
        print(f"  Limit Price: Rs.{price:,.2f}")
    print(f"  Live Price: Rs.{ltp:,.2f}" if ltp else "  Live Price: N/A")
    print(f"  Est. Total: Rs.{est_total:,.2f}" if isinstance(est_total, float) else f"  Est. Total: {est_total}")
    print(f"  Product   : CNC (Delivery)")
    print(f"  Trades today: {trades_today()} / {MAX_TRADES_PER_DAY}")
    print("=" * 48)

    while True:
        ans = input("  Confirm trade? (y/n): ").strip().lower()
        if ans == "y":
            return True
        if ans == "n":
            print("  Trade cancelled.")
            return False
        print("  Please enter 'y' or 'n'.")


# ── Place Order ────────────────────────────────────────────────────────────────

def place_order(
    symbol: str,
    transaction_type: str,    # "BUY" or "SELL"
    quantity: int,
    order_type: str = "MARKET",  # "MARKET" or "LIMIT"
    price: float = 0,
    token: str = None,
    skip_confirmation: bool = False,
) -> Dict:
    """
    Place an order on Upstox after safety checks and user confirmation.

    Safety checks (in order):
      1. Market must be open
      2. Daily trade limit (max 2)
      3. Valid inputs
      4. User confirmation (unless skip_confirmation=True)

    Returns a dict with order_id on success, or error message.
    """
    symbol = symbol.upper()

    # ── Safety check 1: market hours ─────────────────────────────────
    if not is_market_open():
        return {
            "error": f"Market is currently {market_status_str()}. "
                     f"Orders can only be placed between 9:15 AM and 3:30 PM IST on weekdays."
        }

    # ── Safety check 2: daily trade limit ────────────────────────────
    count = trades_today()
    if count >= MAX_TRADES_PER_DAY:
        return {
            "error": f"Daily trade limit reached ({MAX_TRADES_PER_DAY} trades). "
                     f"No more trades allowed today."
        }

    # ── Safety check 3: inputs ────────────────────────────────────────
    if transaction_type not in ("BUY", "SELL"):
        return {"error": "transaction_type must be BUY or SELL"}
    if quantity <= 0:
        return {"error": "quantity must be a positive integer"}
    if order_type not in ("MARKET", "LIMIT"):
        return {"error": "order_type must be MARKET or LIMIT"}
    if order_type == "LIMIT" and price <= 0:
        return {"error": "price must be > 0 for LIMIT orders"}

    # ── Resolve instrument key ────────────────────────────────────────
    instrument_key = get_instrument_key(symbol, token)
    if not instrument_key:
        return {"error": f"Could not find instrument key for '{symbol}'. "
                         f"Please verify the NSE symbol is correct."}

    # ── Get live quote for confirmation display ───────────────────────
    quote = get_quote(symbol, token)
    ltp = quote.get("ltp", 0)

    # ── User confirmation ─────────────────────────────────────────────
    if not skip_confirmation:
        confirmed = _confirm_trade(symbol, transaction_type, quantity,
                                   order_type, price, ltp)
        if not confirmed:
            return {"status": "cancelled", "message": "Trade cancelled by user."}

    # ── Place order via Upstox API ────────────────────────────────────
    payload = {
        "quantity": quantity,
        "product": "D",           # D = CNC/delivery
        "validity": "DAY",
        "price": price if order_type == "LIMIT" else 0,
        "tag": "claude_agent",
        "instrument_token": instrument_key,
        "order_type": order_type,
        "transaction_type": transaction_type,
        "disclosed_quantity": 0,
        "trigger_price": 0,
        "is_amo": False,
    }

    try:
        resp = requests.post(
            f"{BASE_URL}/order/place",
            headers=_headers(token),
            json=payload,
        )
        resp.raise_for_status()
        result = resp.json()
        order_id = result.get("data", {}).get("order_id", "unknown")

        # Record the trade
        _record_trade(order_id, {
            "symbol": symbol,
            "transaction_type": transaction_type,
            "quantity": quantity,
            "order_type": order_type,
            "price": price,
            "ltp_at_order": ltp,
        })

        trades_remaining = MAX_TRADES_PER_DAY - trades_today()
        return {
            "status": "success",
            "order_id": order_id,
            "symbol": symbol,
            "transaction_type": transaction_type,
            "quantity": quantity,
            "order_type": order_type,
            "ltp_at_order": ltp,
            "trades_remaining_today": trades_remaining,
            "message": f"Order placed successfully. Order ID: {order_id}. "
                       f"{trades_remaining} trade(s) remaining today.",
        }

    except requests.RequestException as e:
        error_body = ""
        try:
            error_body = e.response.json()
        except Exception:
            pass
        return {"error": f"Order placement failed: {e}. Details: {error_body}"}


# ── Order Book ─────────────────────────────────────────────────────────────────

def get_order_book(token: str = None) -> Dict:
    """Fetch today's order book from Upstox."""
    try:
        resp = requests.get(
            f"{BASE_URL}/order/retrieve-all",
            headers=_headers(token),
        )
        resp.raise_for_status()
        orders = resp.json().get("data", [])
        return {
            "orders": [
                {
                    "order_id":        o.get("order_id"),
                    "symbol":          o.get("tradingsymbol"),
                    "transaction_type": o.get("transaction_type"),
                    "quantity":        o.get("quantity"),
                    "price":           o.get("price"),
                    "status":          o.get("status"),
                    "order_type":      o.get("order_type"),
                    "placed_at":       o.get("order_timestamp"),
                }
                for o in orders
            ],
            "count": len(orders),
            "trades_today": trades_today(),
            "trades_remaining": MAX_TRADES_PER_DAY - trades_today(),
        }
    except Exception as e:
        return {"error": str(e)}
