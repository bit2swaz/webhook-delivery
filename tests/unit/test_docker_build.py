"""docker image build tests - verify both dockerfiles build without errors.

excluded from normal test runs by default. enable with:
    RUN_DOCKER_TESTS=1 pytest tests/unit/test_docker_build.py -v

requires a running docker daemon.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
RUN_DOCKER_TESTS = os.getenv("RUN_DOCKER_TESTS", "0") == "1"

pytestmark = pytest.mark.skipif(
    not RUN_DOCKER_TESTS,
    reason="set RUN_DOCKER_TESTS=1 to run docker build tests",
)


# ---------------------------------------------------------------------------
# file existence (fast pre-checks before invoking docker)
# ---------------------------------------------------------------------------


def test_api_dockerfile_exists() -> None:
    """docker/Dockerfile must be present."""
    assert (REPO_ROOT / "docker" / "Dockerfile").is_file()


def test_worker_dockerfile_exists() -> None:
    """docker/Dockerfile.worker must be present."""
    assert (REPO_ROOT / "docker" / "Dockerfile.worker").is_file()


def test_dockerignore_exists() -> None:
    """.dockerignore must be present to keep build context small."""
    assert (REPO_ROOT / ".dockerignore").is_file()


def test_production_compose_exists() -> None:
    """docker/docker-compose.yml must be present."""
    assert (REPO_ROOT / "docker" / "docker-compose.yml").is_file()


def test_prometheus_config_exists() -> None:
    """docker/prometheus.yml must be present."""
    assert (REPO_ROOT / "docker" / "prometheus.yml").is_file()


def test_smoke_test_script_exists() -> None:
    """scripts/smoke_test.sh must be present and executable."""
    script = REPO_ROOT / "scripts" / "smoke_test.sh"
    assert script.is_file()
    assert os.access(script, os.X_OK), "smoke_test.sh is not executable"


# ---------------------------------------------------------------------------
# docker build verification (slow - needs docker daemon)
# ---------------------------------------------------------------------------


def test_api_dockerfile_builds_successfully() -> None:
    """docker build -f docker/Dockerfile . exits 0."""
    result = subprocess.run(
        [
            "docker",
            "build",
            "-f",
            "docker/Dockerfile",
            "-t",
            "webhook-api:ci",
            "--no-cache",
            ".",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, (
        f"api docker build failed.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_worker_dockerfile_builds_successfully() -> None:
    """docker build -f docker/Dockerfile.worker . exits 0."""
    result = subprocess.run(
        [
            "docker",
            "build",
            "-f",
            "docker/Dockerfile.worker",
            "-t",
            "webhook-worker:ci",
            "--no-cache",
            ".",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, (
        f"worker docker build failed.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
