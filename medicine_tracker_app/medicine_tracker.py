import json
from datetime import date, datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "medicine_data.json"


def load_data():
    if not DATA_FILE.exists():
        return {"medicines": [], "dose_history": []}

    with DATA_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    data.setdefault("medicines", [])
    data.setdefault("dose_history", [])
    return data


def save_data(data):
    with DATA_FILE.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


def next_medicine_id(medicines):
    if not medicines:
        return 1
    return max(medicine["id"] for medicine in medicines) + 1


def ask_int(message, minimum=0):
    while True:
        value = input(message).strip()
        if not value.isdigit():
            print("Please enter a valid number.")
            continue

        number = int(value)
        if number < minimum:
            print(f"Please enter a number greater than or equal to {minimum}.")
            continue

        return number


def ask_times():
    while True:
        raw_value = input(
            "Enter reminder times separated by commas (example: 08:00,13:00,20:00): "
        ).strip()
        times = [item.strip() for item in raw_value.split(",") if item.strip()]

        if not times:
            print("Please enter at least one time.")
            continue

        valid = True
        for item in times:
            try:
                datetime.strptime(item, "%H:%M")
            except ValueError:
                print(f"'{item}' is not in HH:MM format.")
                valid = False
                break

        if valid:
            return sorted(times)


def add_medicine(data):
    print("\nAdd Medicine")
    name = input("Medicine name: ").strip()
    dosage = input("Dosage (example: 1 tablet): ").strip()
    times = ask_times()
    stock = ask_int("Current stock count: ", minimum=0)
    refill_threshold = ask_int("Low-stock reminder level: ", minimum=0)
    notes = input("Notes (optional): ").strip()

    medicine = {
        "id": next_medicine_id(data["medicines"]),
        "name": name,
        "dosage": dosage,
        "times": times,
        "stock": stock,
        "refill_threshold": refill_threshold,
        "notes": notes,
    }

    data["medicines"].append(medicine)
    save_data(data)
    print(f"{name} was added successfully.")


def list_medicines(data):
    medicines = data["medicines"]
    if not medicines:
        print("\nNo medicines added yet.")
        return

    print("\nYour Medicines")
    for medicine in medicines:
        low_stock = ""
        if medicine["stock"] <= medicine["refill_threshold"]:
            low_stock = " | Refill soon"

        print(
            f"{medicine['id']}. {medicine['name']} | {medicine['dosage']} | "
            f"Times: {', '.join(medicine['times'])} | Stock: {medicine['stock']}{low_stock}"
        )

        if medicine["notes"]:
            print(f"   Notes: {medicine['notes']}")


def find_medicine(data, medicine_id):
    for medicine in data["medicines"]:
        if medicine["id"] == medicine_id:
            return medicine
    return None


def doses_taken_today(data):
    today = date.today().isoformat()
    return {
        (entry["medicine_id"], entry["time"])
        for entry in data["dose_history"]
        if entry["date"] == today
    }


def show_today_schedule(data):
    medicines = data["medicines"]
    if not medicines:
        print("\nNo medicines added yet.")
        return

    taken_today = doses_taken_today(data)
    print(f"\nSchedule for {date.today().isoformat()}")

    for medicine in medicines:
        print(f"{medicine['name']} ({medicine['dosage']})")
        for time_slot in medicine["times"]:
            status = "Taken" if (medicine["id"], time_slot) in taken_today else "Pending"
            print(f"   {time_slot} - {status}")


def mark_dose_taken(data):
    medicines = data["medicines"]
    if not medicines:
        print("\nNo medicines added yet.")
        return

    list_medicines(data)
    medicine_id = ask_int("\nEnter the medicine ID to mark as taken: ", minimum=1)
    medicine = find_medicine(data, medicine_id)

    if not medicine:
        print("Medicine not found.")
        return

    print(f"Available times: {', '.join(medicine['times'])}")
    time_slot = input("Enter the time slot you took: ").strip()

    if time_slot not in medicine["times"]:
        print("That time slot is not listed for this medicine.")
        return

    today = date.today().isoformat()
    for entry in data["dose_history"]:
        if (
            entry["medicine_id"] == medicine["id"]
            and entry["date"] == today
            and entry["time"] == time_slot
        ):
            print("This dose is already marked as taken for today.")
            return

    data["dose_history"].append(
        {
            "medicine_id": medicine["id"],
            "medicine_name": medicine["name"],
            "date": today,
            "time": time_slot,
            "taken_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    )

    if medicine["stock"] > 0:
        medicine["stock"] -= 1

    save_data(data)
    print(f"Marked {medicine['name']} at {time_slot} as taken.")


def restock_medicine(data):
    medicines = data["medicines"]
    if not medicines:
        print("\nNo medicines added yet.")
        return

    list_medicines(data)
    medicine_id = ask_int("\nEnter the medicine ID to restock: ", minimum=1)
    medicine = find_medicine(data, medicine_id)

    if not medicine:
        print("Medicine not found.")
        return

    amount = ask_int("How many units do you want to add? ", minimum=1)
    medicine["stock"] += amount
    save_data(data)
    print(f"Updated stock for {medicine['name']} to {medicine['stock']}.")


def remove_medicine(data):
    medicines = data["medicines"]
    if not medicines:
        print("\nNo medicines added yet.")
        return

    list_medicines(data)
    medicine_id = ask_int("\nEnter the medicine ID to remove: ", minimum=1)
    medicine = find_medicine(data, medicine_id)

    if not medicine:
        print("Medicine not found.")
        return

    data["medicines"] = [
        item for item in data["medicines"] if item["id"] != medicine_id
    ]
    data["dose_history"] = [
        item for item in data["dose_history"] if item["medicine_id"] != medicine_id
    ]
    save_data(data)
    print(f"Removed {medicine['name']} from your tracker.")


def show_history(data):
    history = data["dose_history"]
    if not history:
        print("\nNo doses have been marked as taken yet.")
        return

    print("\nDose History")
    for entry in reversed(history[-10:]):
        print(
            f"{entry['date']} | {entry['medicine_name']} | "
            f"{entry['time']} | Logged at {entry['taken_at']}"
        )


def main():
    data = load_data()

    while True:
        print("\nMedicine Tracker")
        print("1. Add medicine")
        print("2. View all medicines")
        print("3. View today's schedule")
        print("4. Mark dose as taken")
        print("5. Restock medicine")
        print("6. Remove medicine")
        print("7. View dose history")
        print("8. Exit")

        choice = input("Choose an option: ").strip()

        if choice == "1":
            add_medicine(data)
        elif choice == "2":
            list_medicines(data)
        elif choice == "3":
            show_today_schedule(data)
        elif choice == "4":
            mark_dose_taken(data)
        elif choice == "5":
            restock_medicine(data)
        elif choice == "6":
            remove_medicine(data)
        elif choice == "7":
            show_history(data)
        elif choice == "8":
            print("Take care. Your data has been saved.")
            break
        else:
            print("Please choose a valid option from 1 to 8.")


if __name__ == "__main__":
    main()
