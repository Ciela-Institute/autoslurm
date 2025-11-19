import os
from pathlib import Path

__all__ = ["storage_root", "jobs_dir", "slurm_dir", "out_dir", "ensure_storage_dirs", "set_storage_root"]

_override_root: Path | None = None


def set_storage_root(path: Path):
    global _override_root
    _override_root = path


def _root() -> Path:
    if _override_root is not None:
        return _override_root
    return Path(__file__).resolve().parent.parent


def storage_root() -> Path:
    return _root()


def jobs_dir() -> Path:
    return storage_root() / "jobs"


def slurm_dir() -> Path:
    return storage_root() / "slurm"


def out_dir() -> Path:
    return storage_root() / "out"


def ensure_storage_dirs() -> None:
    for path in (jobs_dir(), slurm_dir(), out_dir()):
        path.mkdir(parents=True, exist_ok=True)
