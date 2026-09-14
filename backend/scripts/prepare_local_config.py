#!/usr/bin/env python3
import os
import secrets
from pathlib import Path


def configured_keys(path: Path) -> set[str]:
    if not path.exists():
        return set()
    keys = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            keys.add(stripped.split("=", 1)[0].strip())
    return keys


def main() -> int:
    config_path = Path(os.environ["PMS_CONFIG_FILE"]).expanduser().resolve()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    existing = configured_keys(config_path)
    additions = []
    if "PMS_ENV" not in existing:
        additions.append("PMS_ENV=development")
    if "SECRET_KEY" not in existing:
        additions.append(f"SECRET_KEY={secrets.token_urlsafe(48)}")
    if additions:
        prefix = "\n" if config_path.exists() and config_path.stat().st_size else ""
        with config_path.open("a", encoding="utf-8") as handle:
            handle.write(prefix + "\n".join(additions) + "\n")
    os.chmod(config_path, 0o600)
    print("Local protected configuration is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
