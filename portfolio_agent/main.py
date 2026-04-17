"""
Portfolio Agent — Main Entry Point
────────────────────────────────────
Usage:
  python main.py           # Run once immediately (fetch + analyze + email)
  python main.py --loop    # Run now, then on schedule (every N hours from .env)
  python main.py --login   # First-time Upstox OAuth login
  python main.py --test    # Send a test email with mock data
  python main.py --trade   # Start interactive Claude trading session
  python main.py --weekly  # Generate and email the weekly PDF report
"""

import sys
import os
import argparse
import traceback
from datetime import datetime

sys.path.append(os.path.dirname(__file__))

from collectors.upstox import get_full_portfolio, interactive_login
from collectors.vested import scrape_portfolio
from agent.analyst import analyze_portfolio
from alerts.notifier import send_report, send_error_alert
from config import CHECK_INTERVAL_HOURS


def run_once():
    """Collect data from all sources, analyze, and send the email report."""
    print(f"\n{'='*60}")
    print(f"  Portfolio Agent run started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    try:
        # ── Step 1: Collect Upstox data ──────────────────────────
        print("[1/4] Fetching Upstox portfolio...")
        upstox_data = get_full_portfolio()
        print(f"      Holdings: {len(upstox_data['holdings'])}, "
              f"P&L: ₹{upstox_data['summary'].get('total_pnl', 0):,.2f}")

        # ── Step 2: Collect Vested data ───────────────────────────
        print("\n[2/4] Scraping Vested portfolio...")
        vested_data = scrape_portfolio(headless=True)
        if vested_data.get("error"):
            print(f"      Warning: Vested scrape had an error: {vested_data['error']}")
        else:
            print(f"      Holdings: {len(vested_data['holdings'])}, "
                  f"P&L: ${vested_data['summary'].get('total_pnl_usd', 0):,.2f}")

        # ── Step 3: Analyze with Claude ───────────────────────────
        print("\n[3/4] Running AI analysis...")
        report = analyze_portfolio(upstox_data, vested_data)

        # ── Step 4: Send email ────────────────────────────────────
        print("\n[4/4] Sending email report...")
        send_report(
            report=report,
            upstox_summary=upstox_data.get("summary", {}),
            vested_summary=vested_data.get("summary", {}),
        )

        print(f"\n  Done! Report sent to your email.\n")

    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}"
        print(f"\n[ERROR] {error_msg}")
        try:
            send_error_alert(error_msg)
        except Exception as mail_err:
            print(f"[ERROR] Could not send error alert: {mail_err}")


def run_test():
    """Send a test email using mock data to verify email setup."""
    print("Sending test email with mock data...")

    mock_upstox = {
        "holdings": [
            {"symbol": "INFY", "quantity": 10, "avg_price": 1400, "ltp": 1520,
             "invested_value": 14000, "current_value": 15200, "pnl": 1200, "pnl_pct": 8.57},
            {"symbol": "RELIANCE", "quantity": 5, "avg_price": 2800, "ltp": 2650,
             "invested_value": 14000, "current_value": 13250, "pnl": -750, "pnl_pct": -5.36},
        ],
        "positions": [],
        "summary": {
            "total_invested": 28000, "total_current_value": 28450,
            "total_pnl": 450, "total_pnl_pct": 1.61, "holdings_count": 2,
        },
    }
    mock_vested = {
        "holdings": [
            {"symbol": "AAPL", "quantity": 2, "avg_price": 175.0, "ltp": 189.5,
             "invested_value_usd": 350.0, "current_value_usd": 379.0,
             "pnl_usd": 29.0, "pnl_pct": 8.29},
        ],
        "summary": {
            "total_invested_usd": 350.0, "total_current_value_usd": 379.0,
            "total_pnl_usd": 29.0, "total_pnl_pct": 8.29, "holdings_count": 1,
        },
    }

    from agent.analyst import analyze_portfolio
    report = analyze_portfolio(mock_upstox, mock_vested)

    send_report(
        report=report,
        upstox_summary=mock_upstox["summary"],
        vested_summary=mock_vested["summary"],
        subject="[TEST] Portfolio Agent — Test Email",
    )
    print("Test email sent!")


def run_scheduled():
    """Run on schedule — once immediately then every CHECK_INTERVAL_HOURS hours."""
    import schedule
    import time

    print(f"Starting scheduled mode. Running every {CHECK_INTERVAL_HOURS} hour(s).")
    print("Press Ctrl+C to stop.\n")

    # Run immediately on start
    run_once()

    # Schedule recurring runs
    schedule.every(CHECK_INTERVAL_HOURS).hours.do(run_once)

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Portfolio Monitoring Agent")
    parser.add_argument("--loop",   action="store_true", help="Run on a schedule (loop forever)")
    parser.add_argument("--login",  action="store_true", help="Run first-time Upstox OAuth login")
    parser.add_argument("--test",   action="store_true", help="Send a test email with mock data")
    parser.add_argument("--trade",  action="store_true", help="Start interactive Claude trading session")
    parser.add_argument("--weekly", action="store_true", help="Generate and email weekly PDF report")
    args = parser.parse_args()

    if args.login:
        interactive_login()
    elif args.test:
        run_test()
    elif args.loop:
        run_scheduled()
    elif args.trade:
        from agent.trading_agent import run_trading_session
        run_trading_session()
    elif args.weekly:
        from reports.weekly_report import run_weekly_report
        run_weekly_report()
    else:
        run_once()
