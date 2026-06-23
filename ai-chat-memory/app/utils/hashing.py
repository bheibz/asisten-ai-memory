import hashlib
import json


def hash_prompt(prompt: str, user_id: str = "") -> str:
    raw = f"{user_id}:{prompt}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def hash_dict(data: dict) -> str:
    raw = json.dumps(data, sort_keys=True).encode("utf-8")
    return hashlib.md5(raw).hexdigest()
