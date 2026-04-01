import json
import os
import random
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import lancedb
import numpy as np
import torch


def set_global_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def _as_python(value):
    if hasattr(value, "as_py"):
        value = value.as_py()
    return value


def _get_text(obj) -> str:
    obj = _as_python(obj)
    if obj is None:
        return ""
    if isinstance(obj, dict):
        text = _as_python(obj.get("text"))
        return text.strip() if isinstance(text, str) else ""
    return ""


def extract_positive_pairs_from_lancedb(
    db_dir: Path,
    table_name: str,
    max_pairs: int | None = None,
) -> list[dict[str, str]]:
    db = lancedb.connect(str(db_dir))
    table = db.open_table(table_name)
    search = table.search()
    if max_pairs is not None:
        search = search.limit(max_pairs)
    rows = search.to_arrow().to_pylist()

    pairs: list[dict[str, str]] = []
    for row in rows:
        question_text = _get_text(row.get("question"))
        if not question_text:
            continue

        answers = _as_python(row.get("answers")) or []
        for answer in answers[:1]:
            answer_text = _get_text(answer)
            if answer_text:
                pairs.append({"anchor": question_text, "positive": answer_text})

    return pairs


def split_pairs(
    pairs: list[dict[str, str]],
    eval_ratio: float = 0.05,
    seed: int = 42,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    if not pairs:
        raise ValueError("No pairs to split")

    shuffled = list(pairs)
    rng = random.Random(seed)
    rng.shuffle(shuffled)

    split_idx = max(1, int((1.0 - eval_ratio) * len(shuffled)))
    train_pairs = shuffled[:split_idx]
    eval_pairs = shuffled[split_idx:]
    return train_pairs, eval_pairs


def pairs_to_jsonl(path: Path, pairs: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in pairs:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def find_project_root(start_path: Path) -> Path:
    current = start_path.resolve()
    if current.is_file():
        current = current.parent

    for candidate in [current, *current.parents]:
        if (candidate / "pyproject.toml").exists():
            return candidate

    return start_path.resolve()


def slugify_name(value: str) -> str:
    slug = value.replace("\\", "/").lower()
    slug = re.sub(r"[^a-z0-9/-]+", "-", slug)
    slug = slug.replace("/", "-")
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "training"


def derive_job_basename(training_dir: Path, project_root: Path | None = None) -> str:
    resolved_dir = training_dir.resolve()
    if project_root is not None:
        try:
            rel = resolved_dir.relative_to(project_root.resolve())
            return slugify_name(str(rel))
        except ValueError:
            pass
    return slugify_name(resolved_dir.name)


def build_job_name(
    training_dir: Path,
    project_root: Path | None = None,
    max_length: int = 63,
) -> str:
    basename = derive_job_basename(training_dir, project_root=project_root)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    suffix = f"-{timestamp}"

    if len(basename) + len(suffix) > max_length:
        basename = basename[: max(1, max_length - len(suffix))].rstrip("-")

    return f"{basename}{suffix}".strip("-")


def prepare_dataset_files(
    db_dir: Path,
    table_name: str,
    output_dir: Path,
    seed: int,
    eval_ratio: float = 0.1,
    max_pairs: int | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]], Path, Path]:
    pairs = extract_positive_pairs_from_lancedb(
        db_dir=db_dir,
        table_name=table_name,
        max_pairs=max_pairs,
    )
    if not pairs:
        raise ValueError("No valid question-answer pairs were found in LanceDB.")

    train_pairs, eval_pairs = split_pairs(
        pairs,
        eval_ratio=eval_ratio,
        seed=seed,
    )

    train_channel_dir = output_dir / "train"
    eval_channel_dir = output_dir / "eval"
    train_channel_dir.mkdir(parents=True, exist_ok=True)
    eval_channel_dir.mkdir(parents=True, exist_ok=True)

    train_file = train_channel_dir / "pairs.train.jsonl"
    eval_file = eval_channel_dir / "pairs.eval.jsonl"
    pairs_to_jsonl(train_file, train_pairs)
    pairs_to_jsonl(eval_file, eval_pairs)

    return train_pairs, eval_pairs, train_file, eval_file


def resolve_local_mlflow_tracking_uri(*, port: int = 5000) -> str:
    try:
        docker_host_ip = subprocess.check_output(
            "ip addr show docker0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1",
            shell=True,
            text=True,
        ).strip() or "172.17.0.1"
    except subprocess.CalledProcessError:
        docker_host_ip = "172.17.0.1"

    return f"http://{docker_host_ip}:{port}"


def resolve_managed_mlflow_tracking_uri(project_root: Path) -> str:
    for env_var in ["MLFLOW_TRACKING_URI", "SAGEMAKER_MLFLOW_APP_ARN"]:
        value = os.getenv(env_var)
        if value:
            return value

    terraform_dir = project_root / "terraform"
    if terraform_dir.exists():
        try:
            return subprocess.check_output(
                ["terraform", f"-chdir={terraform_dir}", "output", "-raw", "mlflow_tracking_uri"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

    raise ValueError(
        "Unable to resolve managed MLflow tracking URI. Set MLFLOW_TRACKING_URI or apply Terraform first."
    )


def build_mlflow_environment(
    mode: str,
    experiment_name: str,
    tracking_uri: str | None = None,
    tracking_arn: str | None = None,
) -> dict[str, str]:
    resolved_tracking_uri = tracking_uri

    if not resolved_tracking_uri and mode.lower() == "local":
        resolved_tracking_uri = resolve_local_mlflow_tracking_uri()

    if not resolved_tracking_uri and tracking_arn:
        resolved_tracking_uri = tracking_arn

    if not resolved_tracking_uri:
        raise ValueError(
            "MLflow tracking target is required. Set tracking_uri or tracking_arn."
        )

    env = {
        "MLFLOW_TRACKING_URI": resolved_tracking_uri,
        "MLFLOW_EXPERIMENT_NAME": experiment_name,
    }

    if tracking_arn:
        env["MLFLOW_TRACKING_ARN"] = tracking_arn

    for key in [
        "MLFLOW_TRACKING_TOKEN",
        "MLFLOW_TRACKING_USERNAME",
        "MLFLOW_TRACKING_PASSWORD",
        "MLFLOW_S3_ENDPOINT_URL",
    ]:
        value = os.getenv(key)
        if value:
            env[key] = value

    return env
