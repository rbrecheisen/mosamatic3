import json
from pathlib import Path


class ParamLoader:
    """Mosamatic2-compatible JSON parameter loader.

    The PyTorch model architecture expects ``params.dict[...]`` access, so this
    deliberately preserves the small wrapper used by Mosamatic2.
    """

    def __init__(self, json_path: str | Path):
        self.update(json_path)

    def update(self, json_path: str | Path) -> None:
        with open(json_path, encoding="utf-8") as f:
            params = json.load(f)
        if not isinstance(params, dict):
            raise ValueError(f"{Path(json_path).name} must contain a JSON object")
        self.__dict__.update(params)

    @property
    def dict(self):
        return self.__dict__
