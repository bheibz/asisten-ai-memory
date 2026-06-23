import tiktoken


def count_tokens(text: str, model: str = "gpt-4o-mini") -> int:
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


def count_tokens_messages(messages: list[dict], model: str = "gpt-4o-mini") -> int:
    total = 0
    for msg in messages:
        total += count_tokens(msg.get("content", ""), model)
    return total
