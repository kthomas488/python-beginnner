"""
Upstox Auto Token Refresh
──────────────────────────
Automates the daily Upstox OAuth login using Playwright.

Two modes:
  1. TOTP mode (fully automated) — if UPSTOX_TOTP_SECRET is set in .env
     Upstox supports TOTP as an alternative to SMS OTP.
     To enable: Upstox app → Profile → Security → Enable TOTP
     Copy the TOTP secret into UPSTOX_TOTP_SECRET in .env

  2. Semi-auto mode — opens browser, auto-fills mobile + PIN,
     pauses for you to enter the OTP manually, then captures token.

Run directly to refresh manually:
  python collectors/upstox_auth.py
"""

import os
import sys
import time
import pyotp

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import (
    UPSTOX_CLIENT_ID,
    UPSTOX_CLIENT_SECRET,
    UPSTOX_REDIRECT_URI,
)

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

# Load extra auth env vars directly (may not be in config.py yet)
from dotenv import load_dotenv
load_dotenv()

UPSTOX_MOBILE   = os.getenv("UPSTOX_MOBILE", "")
UPSTOX_PIN      = os.getenv("UPSTOX_PIN", "")
UPSTOX_TOTP_SECRET = os.getenv("UPSTOX_TOTP_SECRET", "")

AUTH_URL = (
    f"https://api.upstox.com/v2/login/authorization/dialog"
    f"?response_type=code"
    f"&client_id={UPSTOX_CLIENT_ID}"
    f"&redirect_uri={UPSTOX_REDIRECT_URI}"
)


def _save_token(token: str):
    """Save the fresh access token to .env."""
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    lines = []
    found = False
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
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
    print("[Auth] New access token saved to .env")


def _exchange_code(auth_code: str) -> str:
    """Exchange OAuth code for an access token."""
    import requests
    url = "https://api.upstox.com/v2/login/authorization/token"
    payload = {
        "code": auth_code,
        "client_id": UPSTOX_CLIENT_ID,
        "client_secret": UPSTOX_CLIENT_SECRET,
        "redirect_uri": UPSTOX_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }
    resp = requests.post(url, data=payload, headers=headers)
    resp.raise_for_status()
    return resp.json()["access_token"]


def _extract_code_from_url(url: str) -> str:
    """Pull the ?code= value from the redirect URL."""
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    codes = params.get("code", [])
    if not codes:
        raise ValueError(f"No 'code' found in redirect URL: {url}")
    return codes[0]


def refresh_token(headless: bool = True) -> str:
    """
    Main entry point. Automates the Upstox login and returns a fresh token.
    Also saves it to .env automatically.
    """
    if not PLAYWRIGHT_AVAILABLE:
        raise RuntimeError("Playwright not installed. Run: pip install playwright && playwright install chromium")

    if not UPSTOX_MOBILE or not UPSTOX_PIN:
        raise ValueError("Set UPSTOX_MOBILE and UPSTOX_PIN in your .env file.")

    use_totp = bool(UPSTOX_TOTP_SECRET)
    mode = "TOTP (fully automated)" if use_totp else "Semi-auto (manual OTP)"
    print(f"[Auth] Starting token refresh — mode: {mode}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        auth_code = None

        # Watch for the redirect to our callback URL
        def on_response(response):
            nonlocal auth_code
            if UPSTOX_REDIRECT_URI.split("://")[1].split("/")[0] in response.url:
                try:
                    auth_code = _extract_code_from_url(response.url)
                except ValueError:
                    pass

        page.on("response", on_response)

        try:
            print(f"[Auth] Opening Upstox login page...")
            page.goto(AUTH_URL, wait_until="networkidle")
            page.wait_for_timeout(2000)

            # ── Step 1: Enter mobile number ──────────────────────────
            mobile_input = page.locator(
                'input[type="text"], input[type="tel"], input[placeholder*="mobile" i], '
                'input[placeholder*="phone" i], input[id*="mobile" i]'
            ).first
            mobile_input.fill(UPSTOX_MOBILE)
            page.wait_for_timeout(500)

            # Click Get OTP / Continue button
            get_otp_btn = page.locator(
                'button:has-text("Get OTP"), button:has-text("Continue"), '
                'button:has-text("Send OTP"), button[type="submit"]'
            ).first
            get_otp_btn.click()
            page.wait_for_timeout(2000)

            # ── Step 2: Enter OTP / TOTP ─────────────────────────────
            otp_input = page.locator(
                'input[type="text"][maxlength="6"], input[placeholder*="OTP" i], '
                'input[placeholder*="otp" i], input[id*="otp" i]'
            ).first

            if use_totp:
                totp = pyotp.TOTP(UPSTOX_TOTP_SECRET)
                otp_code = totp.now()
                print(f"[Auth] Generated TOTP: {otp_code}")
                otp_input.fill(otp_code)
            else:
                # Pause and wait for user to manually enter the OTP
                print("\n[Auth] OTP sent to your mobile. Check browser and enter the OTP.")
                print("[Auth] Waiting up to 60 seconds for you to enter it...")
                # Wait for OTP field to be filled (poll every 2s for up to 60s)
                for _ in range(30):
                    val = otp_input.input_value()
                    if val and len(val) >= 6:
                        break
                    time.sleep(2)

            page.wait_for_timeout(500)

            # Click Continue / Verify
            verify_btn = page.locator(
                'button:has-text("Continue"), button:has-text("Verify"), '
                'button:has-text("Submit"), button[type="submit"]'
            ).first
            verify_btn.click()
            page.wait_for_timeout(2000)

            # ── Step 3: Enter PIN ─────────────────────────────────────
            pin_input = page.locator(
                'input[type="password"], input[placeholder*="pin" i], '
                'input[placeholder*="PIN" i], input[id*="pin" i]'
            ).first
            pin_input.fill(UPSTOX_PIN)
            page.wait_for_timeout(500)

            pin_submit = page.locator(
                'button:has-text("Continue"), button:has-text("Login"), '
                'button:has-text("Submit"), button[type="submit"]'
            ).first
            pin_submit.click()

            # ── Wait for redirect with auth code ──────────────────────
            print("[Auth] Waiting for authorization code...")
            for _ in range(30):
                if auth_code:
                    break
                # Also check current URL
                try:
                    current = page.url
                    if UPSTOX_REDIRECT_URI.split("://")[1].split("/")[0] in current:
                        auth_code = _extract_code_from_url(current)
                        break
                except Exception:
                    pass
                time.sleep(1)

        finally:
            browser.close()

    if not auth_code:
        raise RuntimeError("[Auth] Failed to capture authorization code. Check credentials.")

    print("[Auth] Authorization code captured. Exchanging for token...")
    token = _exchange_code(auth_code)
    _save_token(token)
    print("[Auth] Token refresh complete.")
    return token


if __name__ == "__main__":
    token = refresh_token(headless=False)
    print(f"\nNew token (first 40 chars): {token[:40]}...")
