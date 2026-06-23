import pytest

from app.core.model_router import ModelRouter


@pytest.mark.asyncio
async def test_select_model_default():
    router = ModelRouter()
    model = await router.select_model(complexity="simple", category="casual")
    assert model == "qwen/qwen3-next-80b-a3b-instruct:free"


@pytest.mark.asyncio
async def test_select_model_coding():
    router = ModelRouter()
    model = await router.select_model(complexity="simple", category="coding")
    assert model == "qwen/qwen3-coder:free"


@pytest.mark.asyncio
async def test_select_model_creative():
    router = ModelRouter()
    model = await router.select_model(complexity="creative", category="writing")
    assert model == "meta-llama/llama-3.3-70b-instruct:free"


@pytest.mark.asyncio
async def test_select_model_force_smart():
    router = ModelRouter()
    model = await router.select_model(complexity="simple", category="casual", force_smart=True)
    assert model == "qwen/qwen3-next-80b-a3b-instruct:free"
