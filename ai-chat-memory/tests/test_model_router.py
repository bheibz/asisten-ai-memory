from app.core.model_router import ModelRouter


def test_select_model_default():
    router = ModelRouter()
    model = router.select_model(complexity="simple", category="casual")
    assert model == "oc/deepseek-v4-flash-free"


def test_select_model_coding():
    router = ModelRouter()
    model = router.select_model(complexity="simple", category="coding")
    assert model == "oc/deepseek-v4-flash-free"


def test_select_model_creative():
    router = ModelRouter()
    model = router.select_model(complexity="creative", category="writing")
    assert model == "oc/deepseek-v4-flash-free"


def test_select_model_force_smart():
    router = ModelRouter()
    model = router.select_model(complexity="simple", category="casual", force_smart=True)
    assert model == "oc/deepseek-v4-flash-free"
