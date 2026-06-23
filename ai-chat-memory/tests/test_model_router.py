import pytest

from app.core.model_router import ModelRouter


@pytest.mark.asyncio
async def test_select_model_default():
    router = ModelRouter()
    model = await router.select_model(complexity="simple", category="casual")
    assert model == "deepseek-chat"


@pytest.mark.asyncio
async def test_select_model_coding():
    router = ModelRouter()
    model = await router.select_model(complexity="simple", category="coding")
    assert model == "deepseek-chat"


@pytest.mark.asyncio
async def test_select_model_creative():
    router = ModelRouter()
    model = await router.select_model(complexity="creative", category="writing")
    assert model == "deepseek-chat"


@pytest.mark.asyncio
async def test_select_model_force_smart():
    router = ModelRouter()
    model = await router.select_model(complexity="simple", category="casual", force_smart=True)
    assert model == "deepseek-reasoner"
