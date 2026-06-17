import hashlib
import json
from pathlib import Path

CHECKSUMS_PATH = Path(__file__).with_name("checksums.json")


def load_expected_checksums() -> dict:
    if not CHECKSUMS_PATH.exists():
        return {}
    try:
        return json.loads(CHECKSUMS_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def compute_file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_download(path: Path, expected_hash: str) -> bool:
    if not expected_hash:
        return True
    if not path.exists():
        return False
    return compute_file_sha256(path) == expected_hash.lower()


def verify_download_strict(path: Path, expected_hash: str) -> bool:
    if not expected_hash:
        return False
    return verify_download(path, expected_hash)
