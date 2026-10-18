
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = Path(__file__).resolve().parent

DEFAULTS = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def as_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {
        "true", "1", "yes", "on"
    }

def coerce(key, value):
    if key in ("port", "workers"):
        return int(value)
    if key == "debug":
        return as_bool(value)
    return str(value)

def effective_config(overrides):
    # Layer 1: hardcoded defaults
    config = DEFAULTS.copy()

    # Layer 2: environment-specific YAML
    env_name = os.getenv("APP_ENV", "development")
    yaml_file = BASE_DIR / f"config.{env_name}.yaml"
    if yaml_file.exists():
        with open(yaml_file, encoding="utf-8") as f:
            config.update(yaml.safe_load(f) or {})

    # Layer 3: .env file (lower priority than OS environment)
    load_dotenv(BASE_DIR / ".env", override=False)
    env_file = {}
    from dotenv import dotenv_values
    env_file = dotenv_values(BASE_DIR / ".env")

    if env_file.get("NUM_WORKERS") is not None:
        config["workers"] = env_file["NUM_WORKERS"]
    if env_file.get("APP_PORT") is not None:
        config["port"] = env_file["APP_PORT"]
    if env_file.get("APP_DEBUG") is not None:
        config["debug"] = env_file["APP_DEBUG"]
    if env_file.get("APP_LOG_LEVEL") is not None:
        config["log_level"] = env_file["APP_LOG_LEVEL"]
    if env_file.get("APP_API_KEY") is not None:
        config["api_key"] = env_file["APP_API_KEY"]

    # Layer 4: actual OS environment variables
    mapping = {
        "APP_PORT": "port",
        "APP_WORKERS": "workers",
        "APP_DEBUG": "debug",
        "APP_LOG_LEVEL": "log_level",
        "APP_API_KEY": "api_key",
    }
    for env_key, config_key in mapping.items():
        if env_key in os.environ:
            config[config_key] = os.environ[env_key]

    # Highest precedence: query-string overrides
    for key, value in overrides:
        if key in config:
            config[key] = value

    # Enforce required types and mask the secret
    result = {
        key: coerce(key, value)
        for key, value in config.items()
    }
    result["api_key"] = "****"
    return result

@app.get("/effective-config")
def get_effective_config(
    set: list[str] = Query(default=[])
):
    overrides = []
    for item in set:
        if "=" in item:
            key, value = item.split("=", 1)
            overrides.append((key.strip(), value))
    return effective_config(overrides)

@app.get("/")
def health():
    return {"status": "ok"}
