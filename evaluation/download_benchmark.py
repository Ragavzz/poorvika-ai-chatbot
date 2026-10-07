import os
from pathlib import Path
import requests

DEST_DIR = Path("evaluation/jev_benchmark/dataset")
DEST_DIR.mkdir(parents=True, exist_ok=True)
DEST_FILE = DEST_DIR / "test-00000-of-00001.parquet"

URL = "https://huggingface.co/datasets/LocalLLaMA/typed-decisions/resolve/main/all/test-00000-of-00001.parquet"

if not DEST_FILE.exists():
    print(f"Downloading {URL}...")
    resp = requests.get(URL, stream=True, timeout=60)
    resp.raise_for_status()
    with open(DEST_FILE, "wb") as f:
        for chunk in resp.iter_content(chunk_size=65536):
            if chunk:
                f.write(chunk)
    print(f"Saved to {DEST_FILE} (size: {os.path.getsize(DEST_FILE)} bytes)")
else:
    print(f"File already exists: {DEST_FILE} (size: {os.path.getsize(DEST_FILE)} bytes)")
