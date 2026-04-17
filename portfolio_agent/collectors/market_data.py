"""
Market Data Collector
──────────────────────
Fetches price history, technical indicators, and fundamental data
for NSE-listed stocks using yfinance.

NSE symbol format: SYMBOL.NS  (e.g. MAXHEALTH → MAXHEALTH.NS)
ETFs like NIFTYBEES, GOLDCASE, LIQUIDCASE may not have fundamental data.
"""

import sys
import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf
from ta.momentum import RSIIndicator
from ta.trend import MACD, SMAIndicator, EMAIndicator
from ta.volatility import BollingerBands

sys.path.append(os.path.dirname(os.path.dirname(__file__)))


# ── Helpers ────────────────────────────────────────────────────────────────────

def _nse_symbol(symbol: str) -> str:
    """Convert Upstox trading symbol to yfinance NSE format."""
    # Some ETFs/index funds have different suffixes
    clean = symbol.strip().upper()
    return f"{clean}.NS"


def _safe_round(val, digits: int = 2):
    try:
        return round(float(val), digits) if val is not None else None
    except (TypeError, ValueError):
        return None


# ── Price History ──────────────────────────────────────────────────────────────

def get_price_history(symbol: str, period: str = "6mo") -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV price history for a stock.

    Args:
        symbol: Upstox trading symbol (e.g. 'MAXHEALTH')
        period: yfinance period string ('1mo', '3mo', '6mo', '1y', '2y')

    Returns:
        DataFrame with columns: Open, High, Low, Close, Volume
        or None if data unavailable.
    """
    yf_symbol = _nse_symbol(symbol)
    try:
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(period=period)
        if df.empty:
            print(f"[MarketData] No price data for {yf_symbol}")
            return None
        df.index = pd.to_datetime(df.index)
        return df[["Open", "High", "Low", "Close", "Volume"]].copy()
    except Exception as e:
        print(f"[MarketData] Error fetching price history for {symbol}: {e}")
        return None


# ── Technical Indicators ───────────────────────────────────────────────────────

def get_technicals(symbol: str) -> Dict:
    """
    Calculate key technical indicators for a stock.

    Returns a dict with:
      rsi, rsi_signal, macd, macd_signal, macd_histogram,
      sma_50, sma_200, ema_20, current_price,
      above_sma50, above_sma200, golden_cross,
      bb_upper, bb_lower, bb_pct (Bollinger Band position 0-1)
    """
    df = get_price_history(symbol, period="1y")
    if df is None or len(df) < 30:
        return {"symbol": symbol, "error": "insufficient_data"}

    close = df["Close"]
    result = {"symbol": symbol}

    # ── RSI ──────────────────────────────────────────────────────────
    try:
        rsi = RSIIndicator(close=close, window=14)
        rsi_val = _safe_round(rsi.rsi().iloc[-1])
        result["rsi"] = rsi_val
        if rsi_val is not None:
            if rsi_val >= 70:
                result["rsi_signal"] = "Overbought"
            elif rsi_val <= 30:
                result["rsi_signal"] = "Oversold"
            else:
                result["rsi_signal"] = "Neutral"
    except Exception:
        result["rsi"] = None
        result["rsi_signal"] = "N/A"

    # ── MACD ─────────────────────────────────────────────────────────
    try:
        macd_ind = MACD(close=close)
        result["macd"]           = _safe_round(macd_ind.macd().iloc[-1])
        result["macd_signal"]    = _safe_round(macd_ind.macd_signal().iloc[-1])
        result["macd_histogram"] = _safe_round(macd_ind.macd_diff().iloc[-1])
        hist = result["macd_histogram"]
        result["macd_trend"] = "Bullish" if hist and hist > 0 else "Bearish"
    except Exception:
        result.update({"macd": None, "macd_signal": None, "macd_histogram": None, "macd_trend": "N/A"})

    # ── Moving Averages ───────────────────────────────────────────────
    try:
        current_price = _safe_round(close.iloc[-1])
        result["current_price"] = current_price

        if len(close) >= 50:
            sma50 = _safe_round(SMAIndicator(close=close, window=50).sma_indicator().iloc[-1])
            result["sma_50"] = sma50
            result["above_sma50"] = current_price > sma50 if sma50 else None
        else:
            result["sma_50"] = None
            result["above_sma50"] = None

        if len(close) >= 200:
            sma200 = _safe_round(SMAIndicator(close=close, window=200).sma_indicator().iloc[-1])
            result["sma_200"] = sma200
            result["above_sma200"] = current_price > sma200 if sma200 else None

            # Golden cross: SMA50 above SMA200
            result["golden_cross"] = (
                result["sma_50"] > sma200
                if result["sma_50"] and sma200 else None
            )
        else:
            result["sma_200"] = None
            result["above_sma200"] = None
            result["golden_cross"] = None

        ema20 = _safe_round(EMAIndicator(close=close, window=20).ema_indicator().iloc[-1])
        result["ema_20"] = ema20

    except Exception:
        result.update({"current_price": None, "sma_50": None, "sma_200": None,
                       "ema_20": None, "above_sma50": None, "above_sma200": None,
                       "golden_cross": None})

    # ── Bollinger Bands ───────────────────────────────────────────────
    try:
        bb = BollingerBands(close=close, window=20)
        result["bb_upper"] = _safe_round(bb.bollinger_hband().iloc[-1])
        result["bb_lower"] = _safe_round(bb.bollinger_lband().iloc[-1])
        result["bb_pct"]   = _safe_round(bb.bollinger_pband().iloc[-1], 3)
    except Exception:
        result.update({"bb_upper": None, "bb_lower": None, "bb_pct": None})

    # ── 1-week & 1-month returns ──────────────────────────────────────
    try:
        if len(close) >= 5:
            result["week_return_pct"] = _safe_round((close.iloc[-1] / close.iloc[-5] - 1) * 100)
        if len(close) >= 21:
            result["month_return_pct"] = _safe_round((close.iloc[-1] / close.iloc[-21] - 1) * 100)
    except Exception:
        result["week_return_pct"] = None
        result["month_return_pct"] = None

    return result


# ── Fundamental Data ───────────────────────────────────────────────────────────

def get_fundamentals(symbol: str) -> Dict:
    """
    Fetch fundamental data for a stock via yfinance.

    Returns a dict with:
      pe_ratio, pb_ratio, debt_equity, market_cap,
      revenue_growth, earnings_growth, dividend_yield,
      sector, industry, beta
    """
    yf_symbol = _nse_symbol(symbol)
    result = {"symbol": symbol}

    try:
        ticker = yf.Ticker(yf_symbol)
        info = ticker.info

        result["pe_ratio"]        = _safe_round(info.get("trailingPE"))
        result["pb_ratio"]        = _safe_round(info.get("priceToBook"))
        result["debt_equity"]     = _safe_round(info.get("debtToEquity"))
        result["market_cap"]      = info.get("marketCap")
        result["revenue_growth"]  = _safe_round(info.get("revenueGrowth", 0) * 100 if info.get("revenueGrowth") else None)
        result["earnings_growth"] = _safe_round(info.get("earningsGrowth", 0) * 100 if info.get("earningsGrowth") else None)
        result["dividend_yield"]  = _safe_round(info.get("dividendYield", 0) * 100 if info.get("dividendYield") else None)
        result["sector"]          = info.get("sector", "Unknown")
        result["industry"]        = info.get("industry", "Unknown")
        result["beta"]            = _safe_round(info.get("beta"))
        result["52w_high"]        = _safe_round(info.get("fiftyTwoWeekHigh"))
        result["52w_low"]         = _safe_round(info.get("fiftyTwoWeekLow"))

    except Exception as e:
        print(f"[MarketData] Could not fetch fundamentals for {symbol}: {e}")
        result["error"] = str(e)

    return result


# ── Full analysis for all holdings ────────────────────────────────────────────

def enrich_holdings(holdings: List[Dict]) -> List[Dict]:
    """
    Adds technical and fundamental data to each holding dict.
    Returns enriched list.
    """
    enriched = []
    for holding in holdings:
        symbol = holding.get("symbol", "")
        print(f"[MarketData] Fetching data for {symbol}...")

        h = holding.copy()
        h["technicals"]   = get_technicals(symbol)
        h["fundamentals"] = get_fundamentals(symbol)
        h["price_history"] = get_price_history(symbol, period="6mo")
        enriched.append(h)

    return enriched


# ── Portfolio-level risk metrics ───────────────────────────────────────────────

def compute_risk_metrics(enriched_holdings: List[Dict]) -> Dict:
    """
    Compute portfolio-level risk metrics.

    Returns:
      portfolio_beta, sector_exposure, concentration_risk,
      positions_at_risk (loss > 5%), high_rsi_count, low_rsi_count
    """
    total_value = sum(h.get("current_value", 0) for h in enriched_holdings)

    # Beta (market sensitivity)
    betas, weights = [], []
    for h in enriched_holdings:
        beta = h.get("fundamentals", {}).get("beta")
        val  = h.get("current_value", 0)
        if beta and val:
            betas.append(beta)
            weights.append(val)

    portfolio_beta = None
    if betas and sum(weights) > 0:
        portfolio_beta = round(
            sum(b * w for b, w in zip(betas, weights)) / sum(weights), 2
        )

    # Sector exposure
    sector_exposure = {}
    for h in enriched_holdings:
        sector = h.get("fundamentals", {}).get("sector", "Unknown")
        val = h.get("current_value", 0)
        sector_exposure[sector] = sector_exposure.get(sector, 0) + val

    if total_value > 0:
        sector_exposure = {
            k: round(v / total_value * 100, 1)
            for k, v in sector_exposure.items()
        }

    # Concentration risk
    concentration = []
    for h in enriched_holdings:
        val = h.get("current_value", 0)
        pct = round(val / total_value * 100, 1) if total_value else 0
        if pct >= 20:
            concentration.append({"symbol": h["symbol"], "pct": pct})

    # Positions at risk (loss > 5%)
    at_risk = [
        {"symbol": h["symbol"], "pnl_pct": h.get("pnl_pct", 0)}
        for h in enriched_holdings
        if h.get("pnl_pct", 0) <= -5
    ]

    # Technical signals
    rsi_overbought = [
        h["symbol"] for h in enriched_holdings
        if h.get("technicals", {}).get("rsi_signal") == "Overbought"
    ]
    rsi_oversold = [
        h["symbol"] for h in enriched_holdings
        if h.get("technicals", {}).get("rsi_signal") == "Oversold"
    ]

    return {
        "portfolio_beta":   portfolio_beta,
        "sector_exposure":  sector_exposure,
        "concentration_risk": concentration,
        "positions_at_risk": at_risk,
        "rsi_overbought":   rsi_overbought,
        "rsi_oversold":     rsi_oversold,
        "total_value":      round(total_value, 2),
    }


if __name__ == "__main__":
    # Quick test
    symbol = "MAXHEALTH"
    print(f"\nTechnicals for {symbol}:")
    t = get_technicals(symbol)
    for k, v in t.items():
        if k != "price_history":
            print(f"  {k}: {v}")

    print(f"\nFundamentals for {symbol}:")
    f = get_fundamentals(symbol)
    for k, v in f.items():
        print(f"  {k}: {v}")
