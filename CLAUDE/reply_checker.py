import email as email_lib
import imaplib
import json
import smtplib
import sys
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

from excel_tracker import log_dose_to_excel
from reply_parser import parse_reply


BASE_DIR = Path(__file__).resolve().parent
ALERT_CONFIG_FILE = BASE_DIR / "alert_config.json"
BOT_CONFIG_FILE = BASE_DIR / "bot_config.json"
LOG_FILE = BASE_DIR / "logs" / "reply_log.txt"
EXCEL_FILE = BASE_DIR / "dose_tracker.xlsx"


# ── Utilities ──────────────────────────────────────────────────────────────

def load_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default or {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with Path(path).open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def append_log(message):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"[{timestamp}]  {message}\n")
    print(f"[{timestamp}]  {message}")


# ── Gmail IMAP ─────────────────────────────────────────────────────────────

def extract_reply_text(msg):
    """Pull the user's new text, stripping the quoted original email."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    body = payload.decode("utf-8", errors="ignore")
                    break
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode("utf-8", errors="ignore")

    # Keep only lines that are NOT part of the quoted reply
    lines = [
        line for line in body.splitlines()
        if line.strip()
        and not line.startswith(">")
        and not line.startswith("On ")
        and "wrote:" not in line
    ]
    return "\n".join(lines).strip()


def fetch_replies(email_config):
    """Return a list of unread reply texts from the Gmail inbox."""
    imap = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    imap.login(email_config["sender_email"], email_config["app_password"])
    imap.select("INBOX")

    _, message_ids = imap.search(None, '(UNSEEN SUBJECT "Medicine Reminder")')

    replies = []
    for msg_id in message_ids[0].split():
        _, msg_data = imap.fetch(msg_id, "(RFC822)")
        raw = email_lib.message_from_bytes(msg_data[0][1])
        subject = raw.get("Subject", "")
        sender = raw.get("From", "")

        if subject.lower().startswith("re:") and email_config["receiver_email"] in sender:
            text = extract_reply_text(raw)
            if text:
                replies.append({"id": msg_id, "text": text})
            imap.store(msg_id, "+FLAGS", "\\Seen")

    imap.logout()
    return replies


# ── Medicine Data ──────────────────────────────────────────────────────────

def get_pending_today(data):
    """Return medicines not yet marked taken today."""
    today = datetime.now().date().isoformat()
    taken = {
        (e["medicine_id"], e["time"])
        for e in data.get("dose_history", [])
        if e["date"] == today
    }
    pending = []
    for med in data.get("medicines", []):
        for t in med.get("times", []):
            if (med["id"], t) not in taken:
                pending.append({"name": med["name"], "dosage": med["dosage"], "time": t})
    return pending


def mark_as_taken(data, medicine_name):
    """Mark all pending slots for a medicine as taken today. Returns marked entries."""
    today = datetime.now().date().isoformat()
    taken_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    already_taken = {
        (e["medicine_id"], e["time"])
        for e in data.get("dose_history", [])
        if e["date"] == today
    }
    marked = []
    for med in data.get("medicines", []):
        if med["name"].lower() == medicine_name.lower():
            for t in med.get("times", []):
                if (med["id"], t) not in already_taken:
                    data["dose_history"].append({
                        "medicine_id": med["id"],
                        "medicine_name": med["name"],
                        "date": today,
                        "time": t,
                        "taken_at": taken_at,
                    })
                    med["stock"] = max(0, med.get("stock", 1) - 1)
                    marked.append({"name": med["name"], "dosage": med["dosage"], "time": t})
    return marked


# ── Confirmation Email ─────────────────────────────────────────────────────

def send_confirmation(email_config, marked, pending, excel_path):
    separator = "-" * 42
    lines = ["Medicine Tracker — Update Confirmed", separator, ""]

    if marked:
        lines.append("Marked as taken:")
        for m in marked:
            lines.append(f"  - {m['name']} ({m['dosage']}) at {m['time']}")
    else:
        lines.append("No medicines were updated (already marked or not recognised).")

    lines.append("")

    if pending:
        lines.append("Still pending today:")
        for p in pending:
            lines.append(f"  - {p['name']} ({p['dosage']}) at {p['time']}")
    else:
        lines.append("All medicines taken for today. Well done!")

    lines += ["", separator, "Your updated dose report is attached.", "Stay healthy!"]

    msg = EmailMessage()
    msg["Subject"] = "Medicine Tracker - Update Confirmed"
    msg["From"] = email_config["sender_email"]
    msg["To"] = email_config["receiver_email"]
    msg.set_content("\n".join(lines))

    if excel_path.exists():
        with excel_path.open("rb") as f:
            msg.add_attachment(
                f.read(),
                maintype="application",
                subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                filename=excel_path.name,
            )

    with smtplib.SMTP_SSL(email_config["smtp_server"], email_config["smtp_port"]) as server:
        server.login(email_config["sender_email"], email_config["app_password"])
        server.send_message(msg)


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    alert_config = load_json(ALERT_CONFIG_FILE)
    bot_config = load_json(BOT_CONFIG_FILE)

    email_config = load_json(
        (BASE_DIR / alert_config["email_config_path"]).resolve()
    )
    data_path = (BASE_DIR / alert_config["data_path"]).resolve()

    api_key = bot_config.get("anthropic_api_key", "")
    if not api_key:
        append_log("ERROR: anthropic_api_key missing in bot_config.json")
        sys.exit(1)

    append_log("Checking Gmail for replies...")

    try:
        replies = fetch_replies(email_config)
    except Exception as e:
        append_log(f"ERROR fetching emails: {e}")
        return

    if not replies:
        append_log("No new replies found.")
        return

    data = load_json(data_path, {"medicines": [], "dose_history": []})
    medicines = data.get("medicines", [])

    for reply in replies:
        append_log(f"Reply: {reply['text'][:100]}")

        taken_names = parse_reply(reply["text"], medicines, api_key)
        append_log(f"Claude identified: {taken_names if taken_names else 'none'}")

        all_marked = []
        for name in taken_names:
            marked = mark_as_taken(data, name)
            for entry in marked:
                log_dose_to_excel(EXCEL_FILE, entry)
            all_marked.extend(marked)

        save_json(data_path, data)

        pending = get_pending_today(data)
        send_confirmation(email_config, all_marked, pending, EXCEL_FILE)
        append_log(
            f"Done — {len(all_marked)} dose(s) marked, {len(pending)} still pending."
        )


if __name__ == "__main__":
    main()
