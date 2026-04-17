"""
Upstox Collector
────────────────
Fetches holdings and positions from the Upstox API v2 using direct HTTP calls.
"""

import os
import webbrowser
from typing import List, Dict
import requests

import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import (
    UPSTOX_CLIENT_ID,
    UPSTOX_CLIENT_SECRET,
    UPSTOX_REDIRECT_URI,
    UPSTOX_ACCESS_TOKEN,
)

BASE_URL = "https://api.upstox.com/v2"


# ── HTTP helper ────────────────────────────────────────────────────────────────

def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }


# ── OAuth helpers ──────────────────────────────────────────────────────────────

def get_auth_url() -> str:
    return (
        f"{BASE_URL}/login/authorization/dialog"
        f"?response_type=code"
        f"&client_id={UPSTOX_CLIENT_ID}"
        f"&redirect_uri={UPSTOX_REDIRECT_URI}"
    )


def exchange_code_for_token(auth_code: str) -> str:
    """Exchange the OAuth authorization code for an access token."""
    url = f"{BASE_URL}/login/authorization/token"
    payload = {
        "code": auth_code,
        "client_id": UPSTOX_CLIENT_ID,
        "client_secret": UPSTOX_CLIENT_SECRET,
        "redirect_uri": UPSTOX_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
    response = requests.post(url, data=payload, headers=headers)
    response.raise_for_status()
    token = response.json().get("access_token", "")
    _save_token_to_env(token)
    return token


def _save_token_to_env(token: str):
    """Persist the access token back into the .env file."""
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    lines = []
    found = False
    if os.path.exists(env_path):
        with open(env_path) as f:
            lines = f.readlines()
        for i, line in enumerate(lines):
            if line.startswith("UPSTOX_ACCESS_TOKEN"):
                lines[i] = f"UPSTOX_ACCESS_TOKEN={token}\n"
                found = True
                break
    if not found:
        lines.append(f"UPSTOX_ACCESS_TOKEN={token}\n")
    with open(env_path, "w") as f:
        f.writelines(lines)
    print(f"[Upstox] Access token saved to {env_path}")


# ── Data fetchers ──────────────────────────────────────────────────────────────

def get_holdings(token: str = None) -> List[Dict]:
    """Returns long-term holdings (delivery/CNC positions)."""
    token = token or UPSTOX_ACCESS_TOKEN
    url = f"{BASE_URL}/portfolio/long-term-holdings"

    try:
        response = requests.get(url, headers=_headers(token))
        response.raise_for_status()
        data = response.json().get("data", [])

        holdings = []
        for item in data:
            avg_price = item.get("average_price") or 0
            ltp = item.get("last_price") or 0
            qty = item.get("quantity") or 0
            invested = avg_price * qty
            current = ltp * qty
            pnl = current - invested
            pnl_pct = (pnl / invested * 100) if invested else 0

            holdings.append({
                "source": "Upstox",
                "symbol": item.get("tradingsymbol", ""),
                "isin": item.get("isin", ""),
                "company": item.get("company_name", ""),
                "exchange": item.get("exchange", ""),
                "quantity": qty,
                "avg_price": round(avg_price, 2),
                "ltp": round(ltp, 2),
                "invested_value": round(invested, 2),
                "current_value": round(current, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
            })
        return holdings

    except requests.RequestException as e:
        print(f"[Upstox] Error fetching holdings: {e}")
        return []


def get_positions(token: str = None) -> List[Dict]:
    """Returns intraday / short-term positions."""
    token = token or UPSTOX_ACCESS_TOKEN
    url = f"{BASE_URL}/portfolio/short-term-positions"

    try:
        response = requests.get(url, headers=_headers(token))
        response.raise_for_status()
        data = response.json().get("data", [])

        positions = []
        for item in data:
            pnl = (item.get("realised_profit") or 0) + (item.get("unrealised_profit") or 0)
            positions.append({
                "source": "Upstox",
                "symbol": item.get("tradingsymbol", ""),
                "exchange": item.get("exchange", ""),
                "quantity": item.get("quantity", 0),
                "buy_price": round(item.get("buy_price") or 0, 2),
                "sell_price": round(item.get("sell_price") or 0, 2),
                "ltp": round(item.get("last_price") or 0, 2),
                "pnl": round(pnl, 2),
                "type": "position",
            })
        return positions

    except requests.RequestException as e:
        print(f"[Upstox] Error fetching positions: {e}")
        return []


def get_full_portfolio(token: str = None) -> dict:
    """Returns a combined dict with holdings, positions and summary metrics."""
    holdings = get_holdings(token)
    positions = get_positions(token)

    total_invested = sum(h["invested_value"] for h in holdings)
    total_current = sum(h["current_value"] for h in holdings)
    total_pnl = total_current - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested else 0

    return {
        "holdings": holdings,
        "positions": positions,
        "summary": {
            "total_invested": round(total_invested, 2),
            "total_current_value": round(total_current, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl_pct, 2),
            "holdings_count": len(holdings),
        },
    }


# ── First-time login helper ────────────────────────────────────────────────────

def interactive_login():
    """Guides you through the Upstox OAuth flow interactively."""
    print("\n[Upstox] Starting OAuth login flow...")
    auth_url = get_auth_url()
    print(f"\nOpening browser: {auth_url}\n")
    webbrowser.open(auth_url)

    print("After logging in, Upstox will redirect to your redirect URI.")
    print("Copy the 'code' parameter from the redirected URL and paste it below.\n")
    auth_code = input("Paste authorization code here: ").strip()

    token = exchange_code_for_token(auth_code)
    print(f"\n[Upstox] Login successful! Token saved.")
    return token


if __name__ == "__main__":
    print("Fetching portfolio...")
    portfolio = get_full_portfolio()
    print(f"\nSummary: {portfolio['summary']}")
    for h in portfolio["holdings"]:
        print(f"  {h['symbol']}: qty={h['quantity']}, pnl=₹{h['pnl']} ({h['pnl_pct']}%)")
