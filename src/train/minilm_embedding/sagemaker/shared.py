from __future__ import annotations

import json
import os
import random
from pathlib import Path
import time
from typing import Any

import mlflow
import numpy as np
import torch
from datasets import Dataset
from tokenizers import Tokenizer
from sentence_transformers import (
    SentenceTransformer,
    SentenceTransformerTrainer,
    SentenceTransformerTrainingArguments,
)
from sentence_transformers.evaluation import EmbeddingSimilarityEvaluator
from sentence_transformers.losses import MultipleNegativesRankingLoss
from sentence_transformers.training_args import BatchSamplers
from transformers import EarlyStoppingCallback
import argparse
from pydantic import BaseModel, ConfigDict, ValidationError

MLFLOW_EXPERIMENT_NAME = os.getenv(
    "MLFLOW_EXPERIMENT_NAME",
    "embedding",
)
os.environ.setdefault("MLFLOW_EXPERIMENT_NAME", MLFLOW_EXPERIMENT_NAME)

class HyperparametersModel(BaseModel):
    model_config = ConfigDict(extra="ignore")
    num_train_epochs: float
    per_device_train_batch_size: int
    per_device_eval_batch_size: int
    learning_rate: float
    warmup_ratio: float
    seed: int
    early_stopping_patience: int = 1
    early_stopping_threshold: float = 0.001


def _parse_hyperparameters() -> HyperparametersModel:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=str, default=None)

    args, _ = parser.parse_known_args()

    try:
        payload = HyperparametersModel.model_validate_json(args.json)
    except ValidationError as e:
        raise ValueError(f"Invalid --json payload: {e}") from e

    return payload

def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def read_pairs_jsonl(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not path.exists():
        return rows

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            anchor = payload.get("anchor", "")
            positive = payload.get("positive", "")
            if isinstance(anchor, str) and isinstance(positive, str):
                anchor = anchor.strip()
                positive = positive.strip()
                if anchor and positive:
                    rows.append({"anchor": anchor, "positive": positive})
    return rows


def _rankdata_average_ties(values: list[float]) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64)
    order = np.argsort(arr, kind="mergesort")
    ranks = np.empty(len(arr), dtype=np.float64)

    i = 0
    while i < len(arr):
        j = i
        current = arr[order[i]]
        while j + 1 < len(arr) and arr[order[j + 1]] == current:
            j += 1

        avg_rank = (i + j) / 2.0 + 1.0
        ranks[order[i : j + 1]] = avg_rank
        i = j + 1

    return ranks


def compute_spearman_correlation(x: list[float], y: list[float]) -> float | None:
    if len(x) != len(y) or len(x) < 2:
        return None

    rank_x = _rankdata_average_ties(x)
    rank_y = _rankdata_average_ties(y)

    std_x = float(np.std(rank_x))
    std_y = float(np.std(rank_y))
    if std_x == 0.0 or std_y == 0.0:
        return None

    corr = np.corrcoef(rank_x, rank_y)[0, 1]
    return float(corr)


def build_embedding_similarity_evaluator(
    eval_pairs: list[dict[str, str]],
    seed: int,
) -> EmbeddingSimilarityEvaluator | None:
    if len(eval_pairs) < 2:
        return None

    positives = [pair["positive"] for pair in eval_pairs]
    rng = random.Random(seed)

    sentence1: list[str] = []
    sentence2: list[str] = []
    scores: list[float] = []

    for idx, pair in enumerate(eval_pairs):
        anchor = pair["anchor"]
        positive = pair["positive"]

        # Positive example.
        sentence1.append(anchor)
        sentence2.append(positive)
        scores.append(1.0)

        # One sampled negative example per anchor.
        if len(positives) <= 1:
            continue

        negative_idx = idx
        for _ in range(5):
            candidate_idx = rng.randrange(len(positives))
            if candidate_idx != idx and positives[candidate_idx] != positive:
                negative_idx = candidate_idx
                break

        if negative_idx == idx:
            continue

        sentence1.append(anchor)
        sentence2.append(positives[negative_idx])
        scores.append(0.0)

    if len(set(scores)) < 2:
        return None

    return EmbeddingSimilarityEvaluator(
        sentences1=sentence1,
        sentences2=sentence2,
        scores=scores,
        name="eval",
        similarity_fn_names=["cosine"],
        write_csv=False,
    )


def train_from_pairs(
    train_pairs: list[dict[str, str]],
    eval_pairs: list[dict[str, str]],
    checkpoints_dir: Path,
) -> dict[str, Any]:
    if not train_pairs:
        raise ValueError("No train pairs provided")

    config = _parse_hyperparameters()

    set_seed(config.seed)

    train_dataset = Dataset.from_list(train_pairs)
    eval_dataset = Dataset.from_list(eval_pairs) if eval_pairs else None

    #model = SentenceTransformer("sentence-transformers/static-retrieval-mrl-en-v1")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    loss = MultipleNegativesRankingLoss(model)

    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    
    run_name = os.getenv("MLFLOW_EXPERIMENT_NAME", "embedding") + time.strftime("-%Y-%m-%d-%H:%M:%S")

    mlflow.set_tag("mlflow.runName", run_name)
    training_args = SentenceTransformerTrainingArguments(
        output_dir=str(checkpoints_dir),
        num_train_epochs=config.num_train_epochs,
        per_device_train_batch_size=config.per_device_train_batch_size,
        per_device_eval_batch_size=config.per_device_eval_batch_size,
        learning_rate=config.learning_rate,
        warmup_ratio=config.warmup_ratio,
        fp16=False,
        bf16=True,
        batch_sampler=BatchSamplers.NO_DUPLICATES,
        eval_on_start=True,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=1,
        load_best_model_at_end=True,
        logging_steps=25,
        logging_first_step=True,
        metric_for_best_model="eval_pearson_cosine",
        greater_is_better=True,
        report_to="mlflow",
        seed=config.seed,
    )

    evaluator = build_embedding_similarity_evaluator(eval_pairs, seed=config.seed)

    trainer = SentenceTransformerTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        loss=loss,
        evaluator=evaluator,
        callbacks=[
            EarlyStoppingCallback(
                early_stopping_patience=config.early_stopping_patience,
                early_stopping_threshold=config.early_stopping_threshold,
            )
        ],
    )

    result = trainer.train()
    model.save(str(checkpoints_dir / "final_model"))

    metrics: dict[str, Any] = dict(result.metrics)

    training_step_metrics: list[dict[str, float | None]] = []
    seen_steps: set[int] = set()
    train_steps: list[float] = []
    train_losses: list[float] = []

    for entry in trainer.state.log_history:
        if "learning_rate" not in entry:
            continue

        step = entry.get("step")
        loss = entry.get("loss")
        learning_rate = entry.get("learning_rate")

        if not isinstance(step, (int, float)):
            continue

        step_int = int(step)
        if step_int in seen_steps:
            continue
        seen_steps.add(step_int)

        step_float = float(step)
        loss_float = float(loss) if isinstance(loss, (int, float)) else None
        learning_rate_float = (
            float(learning_rate) if isinstance(learning_rate, (int, float)) else None
        )

        if loss_float is not None:
            train_steps.append(step_float)
            train_losses.append(loss_float)

        spearman_step_vs_loss = compute_spearman_correlation(train_steps, train_losses)

        training_step_metrics.append(
            {
                "step": step_float,
                "epoch": float(entry["epoch"]) if isinstance(entry.get("epoch"), (int, float)) else None,
                "loss": loss_float,
                "learning_rate": learning_rate_float,
                "spearman_step_vs_loss": spearman_step_vs_loss,
            }
        )

    metrics["training_step_metrics"] = training_step_metrics

    return metrics


def train_from_jsonl(
    train_file: Path,
    eval_file: Path,
    checkpoints_dir: Path,
) -> dict[str, Any]:
    train_pairs = read_pairs_jsonl(train_file)
    eval_pairs = read_pairs_jsonl(eval_file)

    if not train_pairs:
        raise ValueError(f"No train pairs found in {train_file}")

    return train_from_pairs(
        train_pairs=train_pairs,
        eval_pairs=eval_pairs,
        checkpoints_dir=checkpoints_dir,
    )
