"""Load Pi SSH credentials from .env (no external dependencies)."""

import os

_ENV_DIR = os.path.dirname(os.path.abspath(__file__))


def load_env() -> None:
    env_file = os.path.join(_ENV_DIR, ".env")
    if not os.path.exists(env_file):
        return
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()


load_env()

PI_HOST = os.environ.get("PI_HOST", "videopi.local")
PI_USER = os.environ.get("PI_USER", "maarten")
PI_PASS = os.environ.get("PI_PASS", "")
