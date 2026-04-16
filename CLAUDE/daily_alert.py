import json
import smtplib
import sys
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "alert_config.json"
LOG_FILE = BASE_DIR / "logs" / "alert_log.txt"


def load_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default or {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def resolve_path(config_path, base):
    """Resolve relative paths against the CLAUDE directory."""
    p = Path(config_path)
    if not p.is_absolute():
        p = (base / p).resolve()
    return p


def load_alert_config():
    config = load_json(CONFIG_FILE)
    if not config:
        print(f"ERROR: {CONFIG_FILE} not found.")
        sys.exit(1)
    return config


def build_schedule(medicines):
    """Group medicines by time slot, sorted chronologically."""
    schedule = {}
    for med in medicines:
        for time_slot in med.get("times", []):
            schedule.setdefault(time_slot, []).append(med)
    return dict(sorted(schedule.items()))


def build_email_body(medicines, day_label):
    schedule = build_schedule(medicines)
    separator = "-" * 48

    lines = [
        f"Good morning! Here is your medicine schedule for today.",
        f"Date: {day_label}",
        "",
        separator,
    ]

    if not schedule:
        lines.append("  No medicines scheduled for today.")
    else:
        for time_slot, meds in schedule.items():
            for med in meds:
                low_stock = ""
                if med.get("stock", 0) <= med.get("refill_threshold", 0):
                    low_stock = f"  [!] Low stock: {med['stock']} left"
                name_col = f"{med['name']:<22}"
                lines.append(f"  {time_slot}  ->  {name_col} {med['dosage']}{low_stock}")
                if med.get("notes"):
                    lines.append(f"               Note: {med['notes']}")

    lines += [separator, "", "Stay healthy!"]
    return "\n".join(lines)


def send_email(email_config, medicines, day_label):
    body = build_email_body(medicines, day_label)

    msg = EmailMessage()
    msg["Subject"] = f"Medicine Reminder -- {day_label}"
    msg["From"] = email_config["sender_email"]
    msg["To"] = email_config["receiver_email"]
    msg.set_content(body)

    with smtplib.SMTP_SSL(email_config["smtp_server"], email_config["smtp_port"]) as server:
        server.login(email_config["sender_email"], email_config["app_password"])
        server.send_message(msg)


def append_log(message):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"[{timestamp}]  {message}\n")


def main():
    alert_config = load_alert_config()

    data_path = resolve_path(alert_config["data_path"], BASE_DIR)
    email_config_path = resolve_path(alert_config["email_config_path"], BASE_DIR)

    data = load_json(data_path, {"medicines": [], "dose_history": []})
    medicines = data.get("medicines", [])

    if not medicines:
        append_log("No medicines found in data file. Alert skipped.")
        print("No medicines found in medicine_data.json.")
        return

    email_config = load_json(email_config_path)
    if not email_config:
        append_log("ERROR: email_config.json not found.")
        print("ERROR: email_config.json not found.")
        sys.exit(1)

    if not email_config.get("enabled", False):
        append_log("Email disabled in email_config.json. Alert skipped.")
        print("Email reminders are disabled. Set 'enabled': true in email_config.json.")
        return

    day_label = datetime.now().strftime("%A, %d %b %Y")

    try:
        send_email(email_config, medicines, day_label)
        append_log(
            f"Daily digest sent to {email_config['receiver_email']} "
            f"({len(medicines)} medicine(s))."
        )
        print(f"Daily alert sent to {email_config['receiver_email']}.")
    except Exception as e:
        append_log(f"ERROR sending email: {e}")
        print(f"Failed to send alert: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
