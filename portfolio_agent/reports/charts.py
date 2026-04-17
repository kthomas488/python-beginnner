"""
Charts Module
──────────────
Generates matplotlib charts for the weekly PDF report.
All charts are saved as temporary PNG files and returned as file paths.
"""

import os
import tempfile
from typing import List, Dict, Optional, Tuple
import matplotlib
matplotlib.use("Agg")  # non-interactive backend for PDF generation
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
import pandas as pd
import numpy as np

# ── Color Palette ──────────────────────────────────────────────────────────────
COLORS = {
    "positive": "#27ae60",
    "negative": "#e74c3c",
    "neutral":  "#3498db",
    "warning":  "#f39c12",
    "bg":       "#f8fafc",
    "dark":     "#2d3748",
    "grid":     "#e2e8f0",
    "palette": [
        "#3498db", "#27ae60", "#e74c3c", "#f39c12", "#9b59b6",
        "#1abc9c", "#e67e22", "#2980b9", "#16a085", "#8e44ad",
    ],
}

CHART_DIR = tempfile.mkdtemp(prefix="portfolio_charts_")


def _save_fig(fig, name: str) -> str:
    path = os.path.join(CHART_DIR, f"{name}.png")
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=COLORS["bg"])
    plt.close(fig)
    return path


def _apply_style(ax, title: str = "", xlabel: str = "", ylabel: str = ""):
    ax.set_facecolor(COLORS["bg"])
    ax.grid(True, color=COLORS["grid"], linewidth=0.5, alpha=0.8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(COLORS["grid"])
    ax.spines["bottom"].set_color(COLORS["grid"])
    if title:
        ax.set_title(title, fontsize=12, fontweight="bold", color=COLORS["dark"], pad=10)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=9, color=COLORS["dark"])
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=9, color=COLORS["dark"])
    ax.tick_params(colors=COLORS["dark"], labelsize=8)


# ── Chart 1: Portfolio Allocation Pie ─────────────────────────────────────────

def allocation_pie(holdings: List[Dict]) -> str:
    """Pie chart of current portfolio value per stock."""
    labels = [h["symbol"] for h in holdings]
    values = [h.get("current_value", 0) for h in holdings]
    colors = COLORS["palette"][:len(labels)]

    fig, ax = plt.subplots(figsize=(7, 5), facecolor=COLORS["bg"])

    wedges, texts, autotexts = ax.pie(
        values,
        labels=labels,
        colors=colors,
        autopct="%1.1f%%",
        startangle=140,
        pctdistance=0.82,
        wedgeprops={"linewidth": 1.5, "edgecolor": "white"},
    )
    for text in texts:
        text.set_fontsize(9)
        text.set_color(COLORS["dark"])
    for at in autotexts:
        at.set_fontsize(8)
        at.set_color("white")
        at.set_fontweight("bold")

    ax.set_title("Portfolio Allocation", fontsize=13, fontweight="bold",
                 color=COLORS["dark"], pad=15)

    total = sum(values)
    ax.text(0, 0, f"₹{total:,.0f}", ha="center", va="center",
            fontsize=11, fontweight="bold", color=COLORS["dark"])

    return _save_fig(fig, "allocation_pie")


# ── Chart 2: P&L Bar Chart ────────────────────────────────────────────────────

def pnl_bar(holdings: List[Dict]) -> str:
    """Horizontal bar chart showing P&L per stock."""
    symbols = [h["symbol"] for h in holdings]
    pnls    = [h.get("pnl", 0) for h in holdings]
    pcts    = [h.get("pnl_pct", 0) for h in holdings]

    # Sort by P&L
    sorted_data = sorted(zip(symbols, pnls, pcts), key=lambda x: x[1])
    symbols, pnls, pcts = zip(*sorted_data) if sorted_data else ([], [], [])

    bar_colors = [COLORS["positive"] if p >= 0 else COLORS["negative"] for p in pnls]

    fig, axes = plt.subplots(1, 2, figsize=(10, max(4, len(symbols) * 0.6)),
                              facecolor=COLORS["bg"])

    # Left: absolute P&L
    bars = axes[0].barh(symbols, pnls, color=bar_colors, edgecolor="white",
                        linewidth=0.5, height=0.6)
    _apply_style(axes[0], title="P&L per Stock (₹)", ylabel="")
    axes[0].axvline(0, color=COLORS["dark"], linewidth=0.8)
    for bar, val in zip(bars, pnls):
        x = bar.get_width()
        axes[0].text(x + (abs(x) * 0.02), bar.get_y() + bar.get_height() / 2,
                     f"₹{val:,.0f}", va="center", fontsize=7.5,
                     color=COLORS["positive"] if val >= 0 else COLORS["negative"])

    # Right: percentage P&L
    bar_colors2 = [COLORS["positive"] if p >= 0 else COLORS["negative"] for p in pcts]
    bars2 = axes[1].barh(symbols, pcts, color=bar_colors2, edgecolor="white",
                          linewidth=0.5, height=0.6)
    _apply_style(axes[1], title="P&L per Stock (%)", ylabel="")
    axes[1].axvline(0, color=COLORS["dark"], linewidth=0.8)
    for bar, val in zip(bars2, pcts):
        x = bar.get_width()
        axes[1].text(x + (abs(x) * 0.02), bar.get_y() + bar.get_height() / 2,
                     f"{val:+.1f}%", va="center", fontsize=7.5,
                     color=COLORS["positive"] if val >= 0 else COLORS["negative"])

    fig.suptitle("Individual Stock Performance", fontsize=13, fontweight="bold",
                 color=COLORS["dark"], y=1.02)
    plt.tight_layout()
    return _save_fig(fig, "pnl_bar")


# ── Chart 3: Technical Chart (price + MAs + RSI) ──────────────────────────────

def technical_chart(symbol: str, df: pd.DataFrame, technicals: Dict) -> str:
    """
    Price chart with SMA lines and RSI subplot for a single stock.
    """
    if df is None or df.empty:
        return None

    fig = plt.figure(figsize=(10, 6), facecolor=COLORS["bg"])
    gs = gridspec.GridSpec(2, 1, height_ratios=[3, 1], hspace=0.08)

    ax_price = fig.add_subplot(gs[0])
    ax_rsi   = fig.add_subplot(gs[1], sharex=ax_price)

    dates = df.index
    close = df["Close"]

    # Price line
    ax_price.plot(dates, close, color=COLORS["neutral"], linewidth=1.5,
                  label="Price", zorder=3)

    # SMA 50
    if technicals.get("sma_50"):
        sma50_series = close.rolling(50).mean()
        ax_price.plot(dates, sma50_series, color=COLORS["warning"],
                      linewidth=1, linestyle="--", label="SMA 50", alpha=0.9)

    # SMA 200
    if technicals.get("sma_200"):
        sma200_series = close.rolling(200).mean()
        ax_price.plot(dates, sma200_series, color=COLORS["negative"],
                      linewidth=1, linestyle="--", label="SMA 200", alpha=0.9)

    # Bollinger Bands
    if technicals.get("bb_upper") and technicals.get("bb_lower"):
        bb_upper = close.rolling(20).mean() + 2 * close.rolling(20).std()
        bb_lower = close.rolling(20).mean() - 2 * close.rolling(20).std()
        ax_price.fill_between(dates, bb_lower, bb_upper,
                              alpha=0.08, color=COLORS["neutral"])

    _apply_style(ax_price, title=f"{symbol} — Technical Chart")
    ax_price.set_ylabel("Price (₹)", fontsize=9, color=COLORS["dark"])
    ax_price.legend(fontsize=8, loc="upper left", framealpha=0.7)
    plt.setp(ax_price.get_xticklabels(), visible=False)

    # RSI
    from ta.momentum import RSIIndicator
    rsi_series = RSIIndicator(close=close, window=14).rsi()
    ax_rsi.plot(dates, rsi_series, color=COLORS["neutral"], linewidth=1.2)
    ax_rsi.axhline(70, color=COLORS["negative"], linewidth=0.8,
                   linestyle="--", alpha=0.7)
    ax_rsi.axhline(30, color=COLORS["positive"], linewidth=0.8,
                   linestyle="--", alpha=0.7)
    ax_rsi.fill_between(dates, rsi_series, 70,
                        where=(rsi_series >= 70), alpha=0.2,
                        color=COLORS["negative"])
    ax_rsi.fill_between(dates, rsi_series, 30,
                        where=(rsi_series <= 30), alpha=0.2,
                        color=COLORS["positive"])
    ax_rsi.set_ylim(0, 100)
    ax_rsi.set_ylabel("RSI", fontsize=9, color=COLORS["dark"])
    _apply_style(ax_rsi)
    ax_rsi.tick_params(axis="x", rotation=30, labelsize=7)

    return _save_fig(fig, f"technical_{symbol}")


# ── Chart 4: Sector Exposure ──────────────────────────────────────────────────

def sector_exposure(sector_data: Dict) -> str:
    """Bar chart of portfolio exposure by sector."""
    if not sector_data:
        return None

    sectors = list(sector_data.keys())
    pcts    = list(sector_data.values())

    sorted_pairs = sorted(zip(pcts, sectors), reverse=True)
    pcts, sectors = zip(*sorted_pairs) if sorted_pairs else ([], [])

    colors = COLORS["palette"][:len(sectors)]
    fig, ax = plt.subplots(figsize=(8, max(3.5, len(sectors) * 0.55)),
                            facecolor=COLORS["bg"])

    bars = ax.barh(sectors, pcts, color=colors, edgecolor="white",
                   linewidth=0.5, height=0.6)
    for bar, val in zip(bars, pcts):
        ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}%", va="center", fontsize=9, color=COLORS["dark"])

    ax.axvline(20, color=COLORS["warning"], linewidth=1, linestyle="--",
               alpha=0.7, label="20% threshold")
    ax.set_xlim(0, max(pcts) * 1.2 if pcts else 100)
    ax.legend(fontsize=8)
    _apply_style(ax, title="Sector Exposure (%)", xlabel="Portfolio Weight (%)")

    return _save_fig(fig, "sector_exposure")


# ── Chart 5: Risk Summary Heatmap ─────────────────────────────────────────────

def risk_heatmap(enriched_holdings: List[Dict]) -> str:
    """
    Table-style heatmap showing risk signals per stock:
    RSI, MACD trend, above/below SMA, P&L status.
    """
    symbols = [h["symbol"] for h in enriched_holdings]
    metrics = ["RSI", "MACD", "vs SMA50", "vs SMA200", "P&L"]
    n = len(symbols)
    m = len(metrics)

    # Build matrix (0=neutral, 1=good, -1=bad)
    matrix = np.zeros((n, m))
    annotations = np.empty((n, m), dtype=object)

    for i, h in enumerate(enriched_holdings):
        t = h.get("technicals", {})
        pnl_pct = h.get("pnl_pct", 0)

        rsi = t.get("rsi")
        if rsi:
            if rsi >= 70:   matrix[i, 0] = -1; annotations[i, 0] = f"{rsi:.0f}\nOB"
            elif rsi <= 30: matrix[i, 0] =  1; annotations[i, 0] = f"{rsi:.0f}\nOS"
            else:           matrix[i, 0] =  0; annotations[i, 0] = f"{rsi:.0f}"
        else:
            annotations[i, 0] = "N/A"

        macd_trend = t.get("macd_trend", "N/A")
        matrix[i, 1] = 1 if macd_trend == "Bullish" else (-1 if macd_trend == "Bearish" else 0)
        annotations[i, 1] = macd_trend[:4]

        above50 = t.get("above_sma50")
        matrix[i, 2] = 1 if above50 else -1 if above50 is False else 0
        annotations[i, 2] = "↑" if above50 else ("↓" if above50 is False else "N/A")

        above200 = t.get("above_sma200")
        matrix[i, 3] = 1 if above200 else -1 if above200 is False else 0
        annotations[i, 3] = "↑" if above200 else ("↓" if above200 is False else "N/A")

        matrix[i, 4] = 1 if pnl_pct >= 0 else -1
        annotations[i, 4] = f"{pnl_pct:+.1f}%"

    cmap = matplotlib.colors.LinearSegmentedColormap.from_list(
        "rg", [COLORS["negative"], "#f5f5f5", COLORS["positive"]]
    )

    fig, ax = plt.subplots(figsize=(9, max(3, n * 0.6 + 1.5)), facecolor=COLORS["bg"])
    im = ax.imshow(matrix, cmap=cmap, vmin=-1, vmax=1, aspect="auto")

    ax.set_xticks(range(m))
    ax.set_xticklabels(metrics, fontsize=10, fontweight="bold", color=COLORS["dark"])
    ax.set_yticks(range(n))
    ax.set_yticklabels(symbols, fontsize=9, color=COLORS["dark"])

    for i in range(n):
        for j in range(m):
            ax.text(j, i, str(annotations[i, j]), ha="center", va="center",
                    fontsize=8, color=COLORS["dark"], fontweight="bold")

    ax.set_title("Risk Signal Heatmap", fontsize=13, fontweight="bold",
                 color=COLORS["dark"], pad=12)
    ax.spines[:].set_visible(False)
    ax.tick_params(length=0)
    plt.tight_layout()

    return _save_fig(fig, "risk_heatmap")


# ── Chart 6: Weekly Performance Bar ───────────────────────────────────────────

def weekly_performance(enriched_holdings: List[Dict]) -> str:
    """Bar chart of 1-week return per stock."""
    data = [
        (h["symbol"], h.get("technicals", {}).get("week_return_pct", 0) or 0)
        for h in enriched_holdings
    ]
    data.sort(key=lambda x: x[1])
    symbols, returns = zip(*data) if data else ([], [])

    colors = [COLORS["positive"] if r >= 0 else COLORS["negative"] for r in returns]

    fig, ax = plt.subplots(figsize=(8, max(4, len(symbols) * 0.55)),
                            facecolor=COLORS["bg"])
    bars = ax.barh(symbols, returns, color=colors, edgecolor="white",
                   linewidth=0.5, height=0.6)
    ax.axvline(0, color=COLORS["dark"], linewidth=0.8)
    for bar, val in zip(bars, returns):
        x = bar.get_width()
        ax.text(x + (0.1 if x >= 0 else -0.1),
                bar.get_y() + bar.get_height() / 2,
                f"{val:+.2f}%", va="center",
                ha="left" if x >= 0 else "right",
                fontsize=8,
                color=COLORS["positive"] if val >= 0 else COLORS["negative"])

    _apply_style(ax, title="1-Week Return per Stock (%)", xlabel="Return (%)")
    return _save_fig(fig, "weekly_performance")
