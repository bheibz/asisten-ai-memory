class ModelRouter:

    MODEL_TIERS = {
        "simple": {
            "primary": "oc/deepseek-v4-flash-free",
            "fallback": "oc/big-pickle",
        },
        "moderate": {
            "primary": "oc/deepseek-v4-flash-free",
            "fallback": "oc/big-pickle",
        },
        "complex": {
            "primary": "oc/deepseek-v4-flash-free",
            "fallback": "oc/big-pickle",
        },
        "creative": {
            "primary": "oc/big-pickle",
            "fallback": "oc/deepseek-v4-flash-free",
        },
        "coding": {
            "primary": "oc/deepseek-v4-flash-free",
            "fallback": "oc/big-pickle",
        },
    }

    def select_model(self, complexity: str = "", category: str = "", token_budget: int = 10000, force_smart: bool = False) -> str:
        return "oc/deepseek-v4-flash-free"
