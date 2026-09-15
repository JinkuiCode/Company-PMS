#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import RuntimeConfigurationError, settings, validate_runtime_config


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expect", choices=("development", "production"))
    args = parser.parse_args()
    if args.expect and settings.PMS_ENV != args.expect:
        print(json.dumps({"valid": False, "environment": settings.PMS_ENV, "issues": ["PMS_ENV"]}))
        return 1
    try:
        validate_runtime_config(settings)
    except RuntimeConfigurationError as exc:
        print(json.dumps({"valid": False, "environment": settings.PMS_ENV, "issues": exc.issues}))
        return 1
    print(json.dumps({"valid": True, "environment": settings.PMS_ENV, "issues": []}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
