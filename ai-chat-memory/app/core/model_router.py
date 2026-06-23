class ModelRouter:

    MODEL_TIERS = {
        "simple": {
            "primary": "oc/north-mini-code-free",
            "fallback": "oc/deepseek-v4-flash-free",
        },
        "moderate": {
            "primary": "oc/mimo-v2.5-free",
            "fallback": "oc/north-mini-code-free",
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
            "primary": "oc/north-mini-code-free",
            "fallback": "oc/deepseek-v4-flash-free",
        },
    }

    def select_model(self, complexity: str, category: str, token_budget: int = 10000) -> str:
        if token_budget < 1000:
            return "oc/north-mini-code-free"
        if category == "coding":
            tier = self.MODEL_TIERS["coding"]
        else:
            tier = self.MODEL_TIERS.get(complexity, self.MODEL_TIERS["moderate"])
        return tier["primary"]
