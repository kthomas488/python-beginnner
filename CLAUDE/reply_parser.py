import json
import anthropic


def parse_reply(reply_text: str, medicines: list, api_key: str) -> list:
    """
    Use Claude to identify which medicines the user confirmed taking.
    Returns a list of medicine names (matched against the medicines list).
    """
    client = anthropic.Anthropic(api_key=api_key)

    medicines_summary = "\n".join(
        f"- {m['name']} ({m['dosage']}) scheduled at {', '.join(m.get('times', []))}"
        for m in medicines
    )

    prompt = f"""You are a medicine intake assistant. A user received a daily medicine reminder email and replied to it.

Their scheduled medicines today are:
{medicines_summary}

The user's reply:
"{reply_text}"

Identify which medicines the user has confirmed taking based on their reply.

Rules:
- If they say "all", "done", "taken all", "yes", "yes all", "all done" — return ALL medicine names
- If they mention specific names — return only those
- Handle partial matches and case-insensitivity (e.g. "para" matches "Paracetamol")
- If they say "none", "not yet", or the reply is unclear — return an empty list
- If they say "skipped X, took the rest" — return all except X

Return ONLY valid JSON in this exact format, no explanation:
{{"taken": ["Exact Medicine Name 1", "Exact Medicine Name 2"]}}

Use the exact medicine names from the list above."""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text.strip()

    try:
        result = json.loads(response_text)
        taken = result.get("taken", [])
        valid_names = {m["name"].lower(): m["name"] for m in medicines}
        return [valid_names[name.lower()] for name in taken if name.lower() in valid_names]
    except (json.JSONDecodeError, KeyError):
        return []
