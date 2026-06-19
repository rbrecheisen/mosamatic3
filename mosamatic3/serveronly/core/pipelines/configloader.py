import json
from pathlib import Path

PIPELINE_CONFIG_DIR = Path(__file__).resolve().parent / "configs"


def list_pipeline_configs() -> list[dict]:
    configs = []

    for path in sorted(PIPELINE_CONFIG_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        configs.append(
            {
                "key": path.stem,
                "name": data.get("name", path.stem),
                "version": data.get("version"),
                "path": str(path),
            }
        )

    return configs


def load_pipeline_config(config_key: str) -> dict:
    safe_key = config_key.replace("/", "").replace("\\", "")
    path = PIPELINE_CONFIG_DIR / f"{safe_key}.json"

    if not path.exists():
        raise FileNotFoundError(f"Pipeline config not found: {config_key}")

    return json.loads(path.read_text(encoding="utf-8"))