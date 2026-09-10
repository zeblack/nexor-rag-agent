import yaml

from app.config import settings


class ModelsRegistry:
    def __init__(self, yaml_path: str):
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self._models = {m["id"]: m["label"] for m in data["allowed_models"]}
        self.default_model = data["default_model"]

    def is_allowed(self, model_id: str) -> bool:
        return model_id in self._models

    def list_models(self) -> list[dict]:
        return [{"id": model_id, "label": label} for model_id, label in self._models.items()]


registry = ModelsRegistry(settings.models_yaml_path)
