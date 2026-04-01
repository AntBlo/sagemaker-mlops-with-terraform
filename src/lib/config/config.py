from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class EnvironmentConfig(BaseModel):
	dataset_two_car_pros: Path
	dataset_youtube_captions: Path

	model_config = ConfigDict(extra="forbid")


@lru_cache(maxsize=1)
def load_environment_config(env_file: Path | None = None) -> EnvironmentConfig:
	root_dir = Path(__file__).resolve().parents[3]
	config_path = env_file or root_dir / "env.json"

	with config_path.open("r", encoding="utf-8") as f:
		payload = json.load(f)

	return EnvironmentConfig.model_validate(payload)


ENV = load_environment_config()
