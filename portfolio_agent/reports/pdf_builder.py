"""
PDF Report Builder
───────────────────
Assembles the weekly portfolio PDF using fpdf2.

Structure:
  Page 1  -Cover
  Page 2  -Portfolio Overview (allocation pie + P&L bar)
  Page 3  -Weekly Performance + Risk Heatmap
  Page 4  -Technical Analysis (charts per stock)
  Page 5  -Fundamental Analysis (table)
  Page 6  -Sector Exposure + Risk Metrics
  Page 7  -AI Narrative (Claude analysis)
"""

import os
from datetime import date, timedelta
from typing import List, Dict, Optional

from fpdf import FPDF

# ── Colors (RGB) ──────────────────────────────────────────────────────────────
C_DARK    = (26,  26,  46)
C_BLUE    = (52, 152, 219)
C_GREEN   = (39, 174,  96)
C_RED     = (231, 76,  60)
C_ORANGE  = (243, 156,  18)
C_BG      = (248, 250, 252)
C_WHITE   = (255, 255, 255)
C_GRAY    = (113, 128, 150)
C_LIGHT   = (226, 232, 240)


class PortfolioReport(FPDF):

    def header(self):
        pass  # custom headers per page

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*C_GRAY)
        self.cell(0, 5,
                  f"Portfolio Weekly Report  |  Generated {date.today().strftime('%d %b %Y')}  "
                  f"|  Page {self.page_no()}",
                  align="C")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _section_title(self, text: str):
        self.set_fill_color(*C_DARK)
        self.set_text_color(*C_WHITE)
        self.set_font("Helvetica", "B", 11)
        self.cell(0, 8, f"  {text}", ln=True, fill=True)
        self.ln(3)

    def _kv_row(self, label: str, value: str, positive: bool = None):
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*C_GRAY)
        self.cell(60, 6, label)
        self.set_font("Helvetica", "B", 9)
        if positive is True:
            self.set_text_color(*C_GREEN)
        elif positive is False:
            self.set_text_color(*C_RED)
        else:
            self.set_text_color(*C_DARK)
        self.cell(0, 6, str(value), ln=True)
        self.set_text_color(*C_DARK)

    def _divider(self):
        self.set_draw_color(*C_LIGHT)
        self.line(self.get_x(), self.get_y(), self.get_x() + 190, self.get_y())
        self.ln(2)

    def _insert_image(self, path: Optional[str], w: int = 180):
        if path and os.path.exists(path):
            self.image(path, x=None, w=w)
            self.ln(3)

    def _table_header(self, cols: List[str], widths: List[int]):
        self.set_fill_color(*C_DARK)
        self.set_text_color(*C_WHITE)
        self.set_font("Helvetica", "B", 8)
        for col, w in zip(cols, widths):
            self.cell(w, 7, col, border=0, fill=True, align="C")
        self.ln()
        self.set_text_color(*C_DARK)

    def _table_row(self, values: List[str], widths: List[int],
                   colors: List = None, fill: bool = False):
        if fill:
            self.set_fill_color(*C_BG)
        self.set_font("Helvetica", "", 8)
        for i, (val, w) in enumerate(zip(values, widths)):
            if colors and colors[i]:
                self.set_text_color(*colors[i])
            else:
                self.set_text_color(*C_DARK)
            self.cell(w, 6, str(val), border=0, fill=fill, align="C")
        self.ln()
        self.set_text_color(*C_DARK)

    # ── Pages ──────────────────────────────────────────────────────────────────

    def cover_page(self, portfolio_summary: Dict, week_label: str):
        self.add_page()

        # Dark header band
        self.set_fill_color(*C_DARK)
        self.rect(0, 0, 210, 80, "F")

        self.set_y(20)
        self.set_text_color(*C_WHITE)
        self.set_font("Helvetica", "B", 26)
        self.cell(0, 12, "Portfolio Weekly Report", align="C", ln=True)
        self.set_font("Helvetica", "", 12)
        self.set_text_color(160, 174, 192)
        self.cell(0, 8, week_label, align="C", ln=True)
        self.set_text_color(*C_WHITE)
        self.set_font("Helvetica", "", 10)
        self.cell(0, 6, "Powered by Claude AI  |  Upstox Analytics", align="C", ln=True)

        # Summary cards
        self.set_y(95)
        self.set_text_color(*C_DARK)

        cards = [
            ("Total Invested",    f"Rs.{portfolio_summary.get('total_invested', 0):,.2f}",    None),
            ("Current Value",     f"Rs.{portfolio_summary.get('total_current_value', 0):,.2f}", None),
            ("Total P&L",         f"Rs.{portfolio_summary.get('total_pnl', 0):,.2f}",
             portfolio_summary.get("total_pnl", 0) >= 0),
            ("Overall Return",    f"{portfolio_summary.get('total_pnl_pct', 0):+.2f}%",
             portfolio_summary.get("total_pnl_pct", 0) >= 0),
        ]

        card_w = 44
        x_start = 11
        for i, (label, val, is_pos) in enumerate(cards):
            x = x_start + i * (card_w + 4)
            # Card box
            self.set_fill_color(*C_WHITE)
            self.set_draw_color(*C_LIGHT)
            self.rect(x, self.get_y(), card_w, 30, "FD")

            # Accent bar
            color = C_GREEN if is_pos is True else (C_RED if is_pos is False else C_BLUE)
            self.set_fill_color(*color)
            self.rect(x, self.get_y(), card_w, 3, "F")

            self.set_xy(x, self.get_y() + 6)
            self.set_font("Helvetica", "", 7)
            self.set_text_color(*C_GRAY)
            self.cell(card_w, 4, label.upper(), align="C")
            self.set_xy(x, self.get_y() + 4)
            self.set_font("Helvetica", "B", 10)
            self.set_text_color(*C_DARK)
            self.cell(card_w, 6, val, align="C")

        self.ln(45)
        self._divider()

        # Holdings count
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*C_GRAY)
        n = portfolio_summary.get("holdings_count", 0)
        self.cell(0, 8, f"{n} holdings  |  Upstox (NSE/BSE)", align="C", ln=True)

    def overview_page(self, pie_path: str, pnl_bar_path: str):
        self.add_page()
        self._section_title("Portfolio Overview")
        self._insert_image(pie_path, w=90)
        self._insert_image(pnl_bar_path, w=180)

    def performance_page(self, weekly_chart_path: str, heatmap_path: str):
        self.add_page()
        self._section_title("Weekly Performance & Risk Signals")
        self._insert_image(weekly_chart_path, w=170)
        self.ln(2)
        self._insert_image(heatmap_path, w=170)

    def technical_page(self, enriched_holdings: List[Dict], chart_paths: Dict):
        self.add_page()
        self._section_title("Technical Analysis")

        cols   = ["Symbol", "Price", "RSI", "Signal", "MACD", "SMA50", "SMA200", "BB%", "1W Ret"]
        widths = [22, 20, 13, 22, 18, 20, 20, 15, 20]

        self._table_header(cols, widths)

        for i, h in enumerate(enriched_holdings):
            t = h.get("technicals", {})
            rsi_val    = t.get("rsi")
            rsi_sig    = t.get("rsi_signal", "N/A")
            macd_trend = t.get("macd_trend", "N/A")
            sma50      = t.get("sma_50")
            sma200     = t.get("sma_200")
            price      = t.get("current_price")
            bb_pct     = t.get("bb_pct")
            week_ret   = t.get("week_return_pct")

            rsi_color = (
                C_RED if rsi_val and rsi_val >= 70
                else C_GREEN if rsi_val and rsi_val <= 30
                else None
            )
            macd_color = C_GREEN if macd_trend == "Bullish" else C_RED if macd_trend == "Bearish" else None
            week_color = C_GREEN if week_ret and week_ret >= 0 else C_RED if week_ret else None

            values = [
                h["symbol"],
                f"Rs.{price:,.1f}" if price else "N/A",
                f"{rsi_val:.1f}" if rsi_val else "N/A",
                rsi_sig,
                macd_trend,
                f"Rs.{sma50:,.1f}" if sma50 else "N/A",
                f"Rs.{sma200:,.1f}" if sma200 else "N/A",
                f"{bb_pct:.2f}" if bb_pct else "N/A",
                f"{week_ret:+.1f}%" if week_ret is not None else "N/A",
            ]
            colors = [None, None, rsi_color, rsi_color, macd_color,
                      None, None, None, week_color]
            self._table_row(values, widths, colors=colors, fill=(i % 2 == 0))

        self.ln(5)

        # Insert individual technical charts (2 per row)
        self._section_title("Price Charts")
        x_positions = [11, 105]
        col = 0
        row_y = self.get_y()

        for h in enriched_holdings:
            symbol = h["symbol"]
            path = chart_paths.get(symbol)
            if not path or not os.path.exists(path):
                continue

            if col == 0:
                row_y = self.get_y()

            x = x_positions[col]
            if self.get_y() + 50 > 270:
                self.add_page()
                row_y = self.get_y()

            self.image(path, x=x, y=row_y, w=90)
            col += 1
            if col >= 2:
                col = 0
                self.set_y(row_y + 52)

        if col == 1:
            self.set_y(row_y + 52)

    def fundamentals_page(self, enriched_holdings: List[Dict]):
        self.add_page()
        self._section_title("Fundamental Analysis")

        cols   = ["Symbol", "Sector", "P/E", "P/B", "D/E", "Rev Gr%", "EPS Gr%", "Div Yld%", "Beta", "52W H/L"]
        widths = [20, 35, 14, 12, 12, 15, 15, 16, 12, 29]

        self._table_header(cols, widths)

        for i, h in enumerate(enriched_holdings):
            f = h.get("fundamentals", {})
            pe    = f.get("pe_ratio")
            pb    = f.get("pb_ratio")
            de    = f.get("debt_equity")
            rev   = f.get("revenue_growth")
            eps   = f.get("earnings_growth")
            div   = f.get("dividend_yield")
            beta  = f.get("beta")
            h52   = f.get("52w_high")
            l52   = f.get("52w_low")
            sector = (f.get("sector") or "Unknown")[:14]

            de_color  = C_RED if de and de > 100 else C_GREEN if de and de < 30 else None
            rev_color = C_GREEN if rev and rev > 0 else C_RED if rev else None
            eps_color = C_GREEN if eps and eps > 0 else C_RED if eps else None

            values = [
                h["symbol"],
                sector,
                f"{pe:.1f}" if pe else "N/A",
                f"{pb:.1f}" if pb else "N/A",
                f"{de:.0f}" if de else "N/A",
                f"{rev:+.1f}" if rev else "N/A",
                f"{eps:+.1f}" if eps else "N/A",
                f"{div:.2f}" if div else "N/A",
                f"{beta:.2f}" if beta else "N/A",
                f"{h52:.0f}/{l52:.0f}" if h52 and l52 else "N/A",
            ]
            colors = [None, None, None, None, de_color,
                      rev_color, eps_color, None, None, None]
            self._table_row(values, widths, colors=colors, fill=(i % 2 == 0))

        # Legend
        self.ln(4)
        self.set_font("Helvetica", "I", 7.5)
        self.set_text_color(*C_GRAY)
        self.multi_cell(0, 4,
            "P/E: Price-to-Earnings  |  P/B: Price-to-Book  |  D/E: Debt-to-Equity  "
            "|  Rev Gr: Revenue Growth  |  EPS Gr: Earnings Growth  |  Beta: Market sensitivity\n"
            "Green = favourable  |  Red = caution  |  N/A = data unavailable (ETFs/index funds may lack fundamental data)"
        )

    def risk_page(self, risk_metrics: Dict, sector_path: str):
        self.add_page()
        self._section_title("Risk Assessment")

        # Sector chart
        self._insert_image(sector_path, w=150)
        self.ln(2)

        # Risk metrics
        self._section_title("Key Risk Metrics")

        beta = risk_metrics.get("portfolio_beta")
        self._kv_row("Portfolio Beta",
                     f"{beta:.2f}" if beta else "N/A",
                     positive=(beta is not None and beta < 1.2))

        at_risk = risk_metrics.get("positions_at_risk", [])
        at_risk_str = ", ".join(f"{x['symbol']} ({x['pnl_pct']:+.1f}%)" for x in at_risk) or "None"
        self._kv_row("Positions at Risk (loss >5%)", at_risk_str,
                     positive=len(at_risk) == 0)

        conc = risk_metrics.get("concentration_risk", [])
        conc_str = ", ".join(f"{x['symbol']} ({x['pct']}%)" for x in conc) or "None"
        self._kv_row("Concentration Risk (>20%)", conc_str,
                     positive=len(conc) == 0)

        overbought = risk_metrics.get("rsi_overbought", [])
        self._kv_row("RSI Overbought (>70)",
                     ", ".join(overbought) or "None",
                     positive=len(overbought) == 0)

        oversold = risk_metrics.get("rsi_oversold", [])
        self._kv_row("RSI Oversold (<30)",
                     ", ".join(oversold) or "None",
                     positive=len(oversold) > 0)

        self.ln(3)
        self._divider()

        # Risk legend
        self.ln(2)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*C_DARK)
        self.cell(0, 6, "How to interpret:", ln=True)
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(*C_GRAY)
        explanations = [
            ("Portfolio Beta < 1.0", "Less volatile than the market"),
            ("Portfolio Beta > 1.2", "More volatile -higher risk/reward"),
            ("Concentration Risk",   "Single stock >20% of portfolio -diversify"),
            ("RSI Overbought",       "Stock may be due for a pullback"),
            ("RSI Oversold",         "Stock may be undervalued -potential buy opportunity"),
        ]
        for label, desc in explanations:
            self.set_text_color(*C_DARK)
            self.set_font("Helvetica", "B", 8)
            self.cell(55, 5, f"  {label}:")
            self.set_font("Helvetica", "", 8)
            self.set_text_color(*C_GRAY)
            self.cell(0, 5, desc, ln=True)

    def ai_narrative_page(self, narrative: str):
        self.add_page()
        self._section_title("AI Analysis -Claude")

        self.set_font("Helvetica", "", 9.5)
        self.set_text_color(*C_DARK)
        self.set_fill_color(*C_BG)
        self.rect(10, self.get_y(), 190, 240, "F")
        self.set_xy(14, self.get_y() + 4)
        self.multi_cell(182, 5.5, narrative)

        self.ln(4)
        self.set_font("Helvetica", "I", 7.5)
        self.set_text_color(*C_GRAY)
        self.multi_cell(0, 4,
            "Disclaimer: This report is auto-generated for informational purposes only. "
            "It is not financial advice. Past performance does not guarantee future results. "
            "Please consult a SEBI-registered financial advisor before making investment decisions.")


def build_report(
    portfolio: Dict,
    enriched_holdings: List[Dict],
    risk_metrics: Dict,
    chart_paths: Dict,
    ai_narrative: str,
    output_path: str,
):
    """
    Assembles the full PDF report.

    Args:
        portfolio:          Output from upstox.get_full_portfolio()
        enriched_holdings:  Output from market_data.enrich_holdings()
        risk_metrics:       Output from market_data.compute_risk_metrics()
        chart_paths:        Dict of chart name → file path
        ai_narrative:       Claude's analysis string
        output_path:        Where to save the PDF
    """
    today = date.today()
    last_friday = today - timedelta(days=(today.weekday() - 4) % 7)
    week_label = f"Week ending {last_friday.strftime('%d %b %Y')}"

    pdf = PortfolioReport(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.set_margins(10, 10, 10)

    pdf.cover_page(portfolio.get("summary", {}), week_label)
    pdf.overview_page(chart_paths.get("allocation_pie"), chart_paths.get("pnl_bar"))
    pdf.performance_page(chart_paths.get("weekly_performance"), chart_paths.get("risk_heatmap"))
    pdf.technical_page(enriched_holdings, {
        h["symbol"]: chart_paths.get(f"technical_{h['symbol']}")
        for h in enriched_holdings
    })
    pdf.fundamentals_page(enriched_holdings)
    pdf.risk_page(risk_metrics, chart_paths.get("sector_exposure"))
    pdf.ai_narrative_page(ai_narrative)

    pdf.output(output_path)
    print(f"[PDF] Report saved to: {output_path}")
    return output_path
