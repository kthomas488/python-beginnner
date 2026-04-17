"""
Claude Trading Agent
─────────────────────
A conversational agent that can analyze your portfolio and execute trades.

Claude is given 4 tools:
  - get_portfolio   : fetch current holdings + P&L
  - get_quote       : get live price for any NSE symbol
  - place_order     : place a BUY/SELL order (always confirms with you first)
  - get_order_book  : see today's placed orders

Usage:
  python agent/trading_agent.py

Example conversations:
  "Analyze my portfolio and suggest a trade"
  "What is the current price of INFY?"
  "Buy 5 shares of FORTIS at market price"
  "Sell 10 shares of NIFTYBEES"
  "Show me today's orders"
"""

import sys
import os
import json
from typing import List, Dict, Any

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import anthropic
from config import ANTHROPIC_API_KEY
from collectors.upstox import get_full_portfolio
from collectors.trade_executor import (
    get_quote,
    place_order,
    get_order_book,
    trades_today,
    market_status_str,
    MAX_TRADES_PER_DAY,
)


# ── System Prompt ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = f"""You are an expert Indian stock market trading assistant with access to
the user's Upstox portfolio. You can analyze holdings, fetch live prices, and execute trades.

IMPORTANT RULES:
1. You can place a maximum of {MAX_TRADES_PER_DAY} trades per day total. Always check the order book first.
2. Always fetch the live quote BEFORE placing any order so the user sees the current price.
3. For BUY orders on new positions: briefly explain your reasoning (technical or fundamental).
4. Never place more than 1 order per conversation turn.
5. All trades are CNC (delivery/long-term), not intraday.
6. If the market is closed, inform the user but you can still analyze and suggest trades.
7. Be concise. Lead with the most important information.
8. Amounts are in Indian Rupees (Rs.).
9. If the user asks about a stock not in their portfolio, use get_quote to check the price first.
"""

# ── Tool Definitions ───────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "get_portfolio",
        "description": (
            "Fetch the user's current Upstox portfolio: all holdings with quantity, "
            "average price, current price, P&L, and overall summary. "
            "Call this first when the user asks about their portfolio or wants trade suggestions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_quote",
        "description": (
            "Get the live Last Traded Price (LTP) for any NSE-listed stock symbol. "
            "Always call this before placing an order so the user knows the current price."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "NSE trading symbol (e.g. INFY, RELIANCE, MAXHEALTH, NIFTYBEES)",
                }
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "place_order",
        "description": (
            "Place a BUY or SELL order on Upstox. "
            "The system will show the user a confirmation prompt before executing. "
            "Always fetch the live quote first. Max 2 trades per day."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "NSE trading symbol",
                },
                "transaction_type": {
                    "type": "string",
                    "enum": ["BUY", "SELL"],
                    "description": "BUY or SELL",
                },
                "quantity": {
                    "type": "integer",
                    "description": "Number of shares",
                },
                "order_type": {
                    "type": "string",
                    "enum": ["MARKET", "LIMIT"],
                    "description": "MARKET executes at current price. LIMIT executes at your specified price.",
                },
                "price": {
                    "type": "number",
                    "description": "Limit price in Rs. Only needed for LIMIT orders. Set to 0 for MARKET.",
                },
            },
            "required": ["symbol", "transaction_type", "quantity", "order_type"],
        },
    },
    {
        "name": "get_order_book",
        "description": (
            "Get today's order book: all orders placed today, their status, "
            "and how many trades remain for the day."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]


# ── Tool Dispatcher ────────────────────────────────────────────────────────────

def _handle_tool(name: str, inputs: Dict) -> str:
    """Execute a tool call and return the result as a string."""
    try:
        if name == "get_portfolio":
            data = get_full_portfolio()
            summary = data.get("summary", {})
            holdings = data.get("holdings", [])
            lines = [
                f"Portfolio Summary:",
                f"  Invested:      Rs.{summary.get('total_invested', 0):,.2f}",
                f"  Current Value: Rs.{summary.get('total_current_value', 0):,.2f}",
                f"  Total P&L:     Rs.{summary.get('total_pnl', 0):,.2f} "
                f"({summary.get('total_pnl_pct', 0):+.2f}%)",
                f"  Holdings: {len(holdings)}",
                "",
                "Holdings:",
            ]
            for h in holdings:
                lines.append(
                    f"  {h['symbol']:<14} qty={h['quantity']:<6} "
                    f"avg=Rs.{h['avg_price']:<10,.2f} ltp=Rs.{h['ltp']:<10,.2f} "
                    f"pnl=Rs.{h['pnl']:>10,.2f} ({h['pnl_pct']:+.2f}%)"
                )
            lines += [
                "",
                f"Market status: {market_status_str()}",
                f"Trades today: {trades_today()} / {MAX_TRADES_PER_DAY}",
            ]
            return "\n".join(lines)

        elif name == "get_quote":
            symbol = inputs.get("symbol", "")
            result = get_quote(symbol)
            if "error" in result:
                return f"Error fetching quote for {symbol}: {result['error']}"
            ltp = result.get("ltp")
            return (
                f"Live quote for {symbol}: Rs.{ltp:,.2f}"
                if ltp else f"Could not fetch live price for {symbol}."
            )

        elif name == "place_order":
            result = place_order(
                symbol=inputs.get("symbol", ""),
                transaction_type=inputs.get("transaction_type", "BUY"),
                quantity=int(inputs.get("quantity", 0)),
                order_type=inputs.get("order_type", "MARKET"),
                price=float(inputs.get("price", 0)),
            )
            return json.dumps(result, indent=2)

        elif name == "get_order_book":
            result = get_order_book()
            if "error" in result:
                return f"Error: {result['error']}"
            orders = result.get("orders", [])
            lines = [
                f"Order Book — Today ({result.get('count', 0)} orders):",
                f"Trades placed: {result.get('trades_today', 0)} / {MAX_TRADES_PER_DAY}",
                f"Trades remaining: {result.get('trades_remaining', 0)}",
                "",
            ]
            if not orders:
                lines.append("No orders placed today.")
            else:
                for o in orders:
                    lines.append(
                        f"  [{o['status']}] {o['transaction_type']} {o['quantity']}x "
                        f"{o['symbol']} @ {o['order_type']} "
                        f"(ID: {o['order_id']})"
                    )
            return "\n".join(lines)

        else:
            return f"Unknown tool: {name}"

    except Exception as e:
        return f"Tool error ({name}): {type(e).__name__}: {e}"


# ── Agentic Loop ───────────────────────────────────────────────────────────────

def run_trading_session():
    """
    Start an interactive trading session with Claude.
    Type 'exit' or 'quit' to end the session.
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    messages: List[Dict[str, Any]] = []

    print("\n" + "=" * 60)
    print("  Claude Trading Agent")
    print("=" * 60)
    print(f"  Market: {market_status_str()}")
    print(f"  Trades today: {trades_today()} / {MAX_TRADES_PER_DAY}")
    print("  Type 'exit' to end session.")
    print("=" * 60 + "\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSession ended.")
            break

        if user_input.lower() in ("exit", "quit", "bye"):
            print("Claude: Goodbye! Stay invested!")
            break

        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        # ── Inner agentic loop (handles multi-step tool use) ──────────
        while True:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )

            # Append assistant response to history
            messages.append({"role": "assistant", "content": response.content})

            # ── End turn: print Claude's text response ────────────────
            if response.stop_reason == "end_turn":
                for block in response.content:
                    if hasattr(block, "text") and block.text:
                        print(f"\nClaude: {block.text}\n")
                break

            # ── Tool use: execute tools and feed results back ─────────
            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        print(f"  [Tool: {block.name}]")
                        result = _handle_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })

                messages.append({"role": "user", "content": tool_results})
                continue

            # Unexpected stop reason
            break


if __name__ == "__main__":
    run_trading_session()
