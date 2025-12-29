import os
from pathlib import Path
from .config import DEFAULT_MODEL_FILENAME

def resolve_model_path() -> str:
    # 1) Env override
    env = os.environ.get("POSE_MODEL_PATH")
    if env:
        p = Path(env).expanduser()
        if p.exists():
            return str(p)
        raise FileNotFoundError(f"POSE_MODEL_PATH set but file not found: {p}")

    # 2) assets/ next to main.py (repo root)
    cwd = Path.cwd()
    candidate = cwd / "assets" / DEFAULT_MODEL_FILENAME
    if candidate.exists():
        return str(candidate)

    # 3) model in cwd
    candidate2 = cwd / DEFAULT_MODEL_FILENAME
    if candidate2.exists():
        return str(candidate2)

    raise FileNotFoundError(
        "Pose model not found.\n"
        "Put it in:\n"
        f"  assets/{DEFAULT_MODEL_FILENAME}\n"
        "or set POSE_MODEL_PATH to its full path."
    )
