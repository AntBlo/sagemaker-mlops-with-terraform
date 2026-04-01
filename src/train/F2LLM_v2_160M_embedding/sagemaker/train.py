from __future__ import annotations

import os
from pathlib import Path

from shared import (
    train_from_jsonl,
)


def _resolve_channel_file(channel_path: Path) -> Path:
    # In local mode, channels can be mounted as a direct file path.
    if channel_path.is_file():
        return channel_path

    preferred = channel_path / "pairs.jsonl"
    if preferred.exists():
        return preferred

    jsonl_files = sorted(channel_path.glob("*.jsonl"))
    if jsonl_files:
        return jsonl_files[0]

    raise FileNotFoundError(f"No .jsonl file found under {channel_path}")


def main() -> None:
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI")
    if tracking_uri:
        print(f"Using MLFLOW_TRACKING_URI={tracking_uri}")

    experiment_name = os.getenv("MLFLOW_EXPERIMENT_NAME")
    if experiment_name:
        print(f"Using MLFLOW_EXPERIMENT_NAME={experiment_name}")

    train_file = _resolve_channel_file(Path("/opt/ml/input/data/train"))
    eval_file = _resolve_channel_file(Path("/opt/ml/input/data/eval"))

    checkpoints_dir = Path("/opt/ml/output/data/checkpoints")

    train_from_jsonl(
        train_file=train_file,
        eval_file=eval_file,
        checkpoints_dir=checkpoints_dir,
    )


if __name__ == "__main__":
    main()
