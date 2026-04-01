import logging
import os
import shutil
import subprocess

from sagemaker.train.local.local_container import _LocalContainer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Patterns excluded from the staged code directory in local-container mode.
# The source_dir is bind-mounted directly by default, so without staging
# everything inside it (including large .venv, artifacts, etc.) is visible
# to the container.
# ---------------------------------------------------------------------------
CODE_STAGE_EXCLUDE: tuple[str, ...] = (
    # Python virtual environments
    ".venv",
    "venv",
    ".env",
    # Python cache / tooling artefacts
    "__pycache__",
    "*.egg-info",
    "*.dist-info",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    # Editor / notebook artefacts
    ".ipynb_checkpoints",
    # Version control
    ".git",
    # Training data / model artefacts (keep source code clean)
    "input",
    "artifacts",
    # JS / frontend tooling
    "node_modules",
    "mlruns",
    # Build outputs
    "dist",
    "build",
)

# ---------------------------------------------------------------------------
# docker compose v2 compatibility fix
# ---------------------------------------------------------------------------

def _patched_get_compose_cmd_prefix(self):
    try:
        # If this command succeeds, prefer Compose v2 regardless of version string format.
        subprocess.check_output(
            ["docker", "compose", "version"],
            stderr=subprocess.DEVNULL,
            encoding="UTF-8",
        )
        return ["docker", "compose"]
    except Exception:
        pass

    if shutil.which("docker-compose") is not None:
        return ["docker-compose"]

    raise ImportError(
        "Docker Compose is not installed. Local mode requires either 'docker compose' or 'docker-compose'."
    )


def patch_sagemaker():
    _LocalContainer._get_compose_cmd_prefix = _patched_get_compose_cmd_prefix
