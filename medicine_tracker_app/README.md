# Medicine Tracker App

This is a simple Python medicine tracking app with optional email reminders.

## Files in this folder

- `medicine_tracker.py` - main app for adding and managing medicines
- `medicine_data.json` - stores your medicine list and dose history
- `email_reminder.py` - checks whether any medicine is due and sends email reminders
- `email_config.json` - your email reminder settings
- `email_reminder_state.json` - keeps track of reminders already sent

## How to run the medicine tracker

Open PowerShell in this folder and run:

```powershell
python medicine_tracker.py
```

You can also run it from the project root with:

```powershell
python medicine_tracker_app/medicine_tracker.py
```

## App features

- add a medicine
- view all medicines
- view today's schedule
- mark a dose as taken
- restock medicine
- remove medicine
- view dose history

## How to use email reminders

1. Open `email_config.json`
2. Change the values:
   - `"enabled"` to `true`
   - `"sender_email"` to your email address
   - `"app_password"` to your email app password
   - `"receiver_email"` to the email address where you want reminders

For Gmail, use a Gmail app password instead of your normal password.

## How to run the email reminder checker

Run:

```powershell
python email_reminder.py
```

Or from the project root:

```powershell
python medicine_tracker_app/email_reminder.py
```

The script will:

- check the current time
- compare it with medicine reminder times
- skip medicines already marked as taken today
- send an email if a medicine is due now
- save reminder state so it does not send duplicates every time

## Suggested workflow

1. Add medicines using `medicine_tracker.py`
2. Update `email_config.json`
3. Test email reminders by setting a medicine time close to the current time
4. Run `email_reminder.py`

## Optional next step

You can automate reminders by scheduling:

```powershell
python email_reminder.py
```

to run every minute using Windows Task Scheduler.
