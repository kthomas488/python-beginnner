"""
Weekly Report Orchestrator
───────────────────────────
Ties everything together:
  1. Refresh Upstox token
  2. Fetch portfolio from Upstox
  3. Enrich with market data (technicals + fundamentals)
  4. Generate all charts
  5. Run Claude AI analysis
  6. Build PDF
  7. Email the PDF as an attachment

Run manually:
  python reports/weekly_report.py
"""

import os
import sys
import smtplib
import traceback
from datetime import date
from email.message import EmailMessage
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from collectors.upstox import get_full_portfolio
from collectors.market_data import enrich_holdings, compute_risk_metrics
from reports import charts as C
from reports.pdf_builder import build_report
from config import (
    ANTHROPIC_API_KEY,
    ALERT_FROM_EMAIL,
    ALERT_FROM_PASSWORD,
    ALERT_TO_EMAIL,
    UPSTOX_ACCESS_TOKEN,
)

OUTPUT_DIR = Path(__file__).parent.parent / "reports" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ── AI Narrative ───────────────────────────────────────────────────────────────

def generate_narrative(portfolio: dict, enriched: list, risk: dict) -> str:
    """Generate a Claude AI written analysis for the report."""
    import anthropic
    from datetime import date as dt

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    summary = portfolio.get("summary", {})
    holdings_text = "\n".join([
        f"  {h['symbol']}: qty={h['quantity']}, avg=Rs.{h['avg_price']}, "
        f"ltp=Rs.{h['ltp']}, pnl=Rs.{h['pnl']} ({h['pnl_pct']:+.1f}%), "
        f"RSI={h.get('technicals', {}).get('rsi', 'N/A')}, "
        f"MACD={h.get('technicals', {}).get('macd_trend', 'N/A')}, "
        f"PE={h.get('fundamentals', {}).get('pe_ratio', 'N/A')}, "
        f"Beta={h.get('fundamentals', {}).get('beta', 'N/A')}"
        for h in enriched
    ])

    risk_text = (
        f"Portfolio Beta: {risk.get('portfolio_beta', 'N/A')}\n"
        f"Positions at risk (loss >5%): {[x['symbol'] for x in risk.get('positions_at_risk', [])]}\n"
        f"Concentration risk (>20%): {[x['symbol'] for x in risk.get('concentration_risk', [])]}\n"
        f"RSI Overbought: {risk.get('rsi_overbought', [])}\n"
        f"RSI Oversold: {risk.get('rsi_oversold', [])}\n"
        f"Sector Exposure: {risk.get('sector_exposure', {})}"
    )

    prompt = f"""You are a portfolio analyst. Write a concise weekly portfolio review for the week ending {dt.today().strftime('%d %b %Y')}.

PORTFOLIO SUMMARY:
  Invested:      Rs.{summary.get('total_invested', 0):,.2f}
  Current Value: Rs.{summary.get('total_current_value', 0):,.2f}
  Total P&L:     Rs.{summary.get('total_pnl', 0):,.2f} ({summary.get('total_pnl_pct', 0):+.2f}%)

HOLDINGS (with technicals & fundamentals):
{holdings_text}

RISK METRICS:
{risk_text}

Write a structured report with these sections:
1. PORTFOLIO HEALTH VERDICT (one line: Healthy / Caution / At Risk + brief reason)
2. THIS WEEK'S HIGHLIGHTS (2-3 bullet points — top movers, key events)
3. TECHNICAL OUTLOOK (brief per-stock signal: bullish/bearish/neutral)
4. FUNDAMENTAL CONCERNS (any overvalued/undervalued stocks, debt concerns)
5. RISK ALERTS (specific risks to watch next week)
6. ACTIONABLE SUGGESTIONS (2-3 concrete observations — NOT financial advice)

Keep each section concise. Use plain text (no markdown). Total length: ~400 words."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text


# ── Email with PDF ─────────────────────────────────────────────────────────────

def send_pdf_email(pdf_path: str):
    """Email the PDF report as an attachment."""
    today = date.today().strftime("%d %b %Y")
    subject = f"Portfolio Weekly Report — {today}"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"]    = ALERT_FROM_EMAIL
    msg["To"]      = ALERT_TO_EMAIL
    msg.set_content(
        f"Hi,\n\nPlease find attached your portfolio weekly report for {today}.\n\n"
        "This report includes:\n"
        "  - Portfolio overview & allocation\n"
        "  - Technical analysis (RSI, MACD, Moving Averages)\n"
        "  - Fundamental analysis (P/E, P/B, D/E)\n"
        "  - Risk assessment\n"
        "  - AI-generated narrative by Claude\n\n"
        "Stay healthy and invest wisely!\n\n"
        "-- Your Portfolio Agent"
    )

    with open(pdf_path, "rb") as f:
        msg.add_attachment(
            f.read(),
            maintype="application",
            subtype="pdf",
            filename=os.path.basename(pdf_path),
        )

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(ALERT_FROM_EMAIL, ALERT_FROM_PASSWORD)
        server.send_message(msg)

    print(f"[WeeklyReport] PDF emailed to {ALERT_TO_EMAIL}")


# ── Main Orchestrator ──────────────────────────────────────────────────────────

def run_weekly_report():
    print("\n" + "=" * 60)
    print("  Weekly Portfolio Report — Starting")
    print("=" * 60 + "\n")

    try:
        # ── 1. Fetch portfolio ───────────────────────────────────
        print("[1/6] Fetching Upstox portfolio...")
        portfolio = get_full_portfolio()
        holdings  = portfolio.get("holdings", [])
        if not holdings:
            print("No holdings found. Aborting.")
            return
        print(f"      {len(holdings)} holdings fetched.")

        # ── 2. Enrich with market data ───────────────────────────
        print("\n[2/6] Fetching market data (technicals + fundamentals)...")
        enriched = enrich_holdings(holdings)
        risk     = compute_risk_metrics(enriched)
        print(f"      Done. Portfolio beta: {risk.get('portfolio_beta', 'N/A')}")

        # ── 3. Generate charts ───────────────────────────────────
        print("\n[3/6] Generating charts...")
        chart_paths = {}

        chart_paths["allocation_pie"]    = C.allocation_pie(enriched)
        chart_paths["pnl_bar"]           = C.pnl_bar(enriched)
        chart_paths["weekly_performance"]= C.weekly_performance(enriched)
        chart_paths["risk_heatmap"]      = C.risk_heatmap(enriched)
        chart_paths["sector_exposure"]   = C.sector_exposure(risk.get("sector_exposure", {}))

        for h in enriched:
            symbol = h["symbol"]
            df     = h.get("price_history")
            tech   = h.get("technicals", {})
            path   = C.technical_chart(symbol, df, tech)
            if path:
                chart_paths[f"technical_{symbol}"] = path

        print(f"      {len(chart_paths)} charts generated.")

        # ── 4. AI narrative ──────────────────────────────────────
        print("\n[4/6] Generating Claude AI narrative...")
        narrative = generate_narrative(portfolio, enriched, risk)
        print("      Narrative complete.")

        # ── 5. Build PDF ─────────────────────────────────────────
        print("\n[5/6] Building PDF report...")
        filename   = f"portfolio_report_{date.today().strftime('%Y-%m-%d')}.pdf"
        output_path = str(OUTPUT_DIR / filename)
        build_report(portfolio, enriched, risk, chart_paths, narrative, output_path)

        # ── 6. Email PDF ─────────────────────────────────────────
        print("\n[6/6] Sending email with PDF attachment...")
        send_pdf_email(output_path)

        print(f"\n  Done! Report saved to {output_path} and emailed.")

    except Exception as e:
        err = f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}"
        print(f"\n[ERROR] {err}")
        # Try sending error alert
        try:
            from alerts.notifier import send_error_alert
            send_error_alert(f"Weekly report failed:\n\n{err}")
        except Exception:
            pass


if __name__ == "__main__":
    run_weekly_report()
