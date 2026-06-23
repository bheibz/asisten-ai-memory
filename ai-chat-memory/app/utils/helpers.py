import uuid


def generate_id() -> str:
    return str(uuid.uuid4())


def safe_truncate(text: str, max_chars: int = 1000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."
