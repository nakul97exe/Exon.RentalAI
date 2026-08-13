import re
import json

def extract_json(raw: str) -> dict:
    """Pull a JSON object out of the model's reply.

    Models often ignore "no markdown fences" and wrap the JSON, or add a sentence
    before it. Slicing from the first { to the last } handles both.
    """
    text = raw.strip()

    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()

    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object in reply: {raw[:200]}")

    return json.loads(text[start : end + 1])