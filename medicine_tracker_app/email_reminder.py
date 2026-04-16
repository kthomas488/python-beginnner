import json
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "medicine_data.json"
CONFIG_FILE = BASE_DIR / "email_config.json"
STATE_FILE = BASE_DIR / "email_reminder_state.json"


def load_json_file(path, default):
    if not path.exists():
        return default

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(default, dict):
        merged = default.copy()
        merged.update(data)
        return merged

    return data


def save_json_file(path, data):
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


def load_medicine_data():
    data = load_json_file(DATA_FILE, {"medicines": [], "dose_history": []})
    data.setdefault("medicines", [])
    data.setdefault("dose_history", [])
    return data


def load_email_config():
    return load_json_file(
        CONFIG_FILE,
        {
            "enabled": False,
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 465,
            "sender_email": "your_email@gmail.com",
            "app_password": "your_app_password",
            "receiver_email": "your_email@gmail.com",
        },
    )


def load_state():
    state = load_json_file(STATE_FILE, {"sent_reminders": []})
    state.setdefault("sent_reminders", [])
    return state


def make_reminder_key(today, medicine_id, time_slot):
    return f"{today}|{medicine_id}|{time_slot}"


def doses_taken_today(data):
    today = datetime.now().date().isoformat()
    return {
        (entry["medicine_id"], entry["time"])
        for entry in data["dose_history"]
        if entry["date"] == today
    }


def due_medicines(data, state):
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    today = now.date().isoformat()
    taken_today = doses_taken_today(data)
    sent_reminders = set(state["sent_reminders"])
    due_items = []

    for medicine in data["medicines"]:
        for time_slot in medicine.get("times", []):
            reminder_key = make_reminder_key(today, medicine["id"], time_slot)
            already_taken = (medicine["id"], time_slot) in taken_today

            if time_slot == current_time and not already_taken and reminder_key not in sent_reminders:
                due_items.append(
                    {
                        "medicine": medicine,
                        "time_slot": time_slot,
                        "reminder_key": reminder_key,
                    }
                )

    return due_items


def build_email_message(config, due_items):
    lines = [
        "This is your medicine reminder.",
        "",
        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "Medicines due now:",
    ]

    for item in due_items:
        medicine = item["medicine"]
        low_stock_note = ""
        if medicine["stock"] <= medicine["refill_threshold"]:
            low_stock_note = " | Low stock warning"

        lines.append(
            f"- {medicine['name']} ({medicine['dosage']}) at {item['time_slot']}{low_stock_note}"
        )

        if medicine.get("notes"):
            lines.append(f"  Notes: {medicine['notes']}")

    message = EmailMessage()
    message["Subject"] = "Medicine Reminder"
    message["From"] = config["sender_email"]
    message["To"] = config["receiver_email"]
    message.set_content("\n".join(lines))
    return message


def send_email(config, due_items):
    message = build_email_message(config, due_items)

    with smtplib.SMTP_SSL(config["smtp_server"], config["smtp_port"]) as server:
        server.login(config["sender_email"], config["app_password"])
        server.send_message(message)


def validate_config(config):
    required_keys = [
        "smtp_server",
        "smtp_port",
        "sender_email",
        "app_password",
        "receiver_email",
    ]

    for key in required_keys:
        if not config.get(key):
            raise ValueError(f"Missing email config value: {key}")

    placeholder_values = {
        "your_email@gmail.com",
        "your_app_password",
    }
    if config["sender_email"] in placeholder_values or config["app_password"] in placeholder_values:
        raise ValueError("Update email_config.json with your real email details before running reminders.")


def main():
    config = load_email_config()
    if not config.get("enabled", False):
        print("Email reminders are disabled. Set 'enabled' to true in email_config.json.")
        return

    validate_config(config)
    data = load_medicine_data()
    state = load_state()
    due_items = due_medicines(data, state)

    if not due_items:
        print("No medicine reminders are due right now.")
        return

    send_email(config, due_items)

    for item in due_items:
        state["sent_reminders"].append(item["reminder_key"])

    save_json_file(STATE_FILE, state)
    print(f"Sent {len(due_items)} medicine reminder email(s).")


if __name__ == "__main__":
    main()
