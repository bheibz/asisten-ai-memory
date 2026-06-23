from app.core.token_counter import count_tokens


def test_count_tokens_empty():
    assert count_tokens("") >= 0


def test_count_tokens_short():
    t = count_tokens("halo")
    assert t > 0


def test_count_tokens_long():
    t = count_tokens("ini adalah kalimat yang cukup panjang untuk test token counting")
    assert t > 5
    assert t < 50
