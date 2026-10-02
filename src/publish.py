#!/usr/bin/env python3
"""Push the frozen rasters, their COGs, the catalogue and the card to the Hugging Face Hub.

The 1,024 originals under raw/ are WorldPop's own bytes, each checked against
the sha256 recorded in scripts/REFERENCE.json, and go up unchanged beside the
1,024 COGs made from them. About 8.4 GB in 2,000 files. huggingface_hub 2.x
has no upload_large_folder; its upload_folder streams through hf_xet and
commits a large folder in several batches by itself.

    uv run python src/publish.py             # dry run
    uv run python src/publish.py --push
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = "yuiseki/worldpop-jp-2026-01"
REFERENCE = ROOT / "scripts" / "REFERENCE.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--push", action="store_true")
    a = ap.parse_args()

    data = ROOT / "data"
    card = (data / "README.md").read_text(encoding="utf-8")
    if "data_files: parquet/files.parquet" not in card:
        raise SystemExit("the card does not declare parquet/files.parquet")
    ref = json.loads(REFERENCE.read_text())
    for rel, r in ref.items():
        for p in (data / "raw" / rel, data / "cog" / rel):
            if not p.exists():
                raise SystemExit(f"missing {p.relative_to(data)}; run scripts/01 and 03 first")
        if sha256(data / "raw" / rel) != r["source_sha256"]:
            raise SystemExit(f"raw/{rel} is not the recorded file")
    print(f"{len(ref)} originals match the reference")

    files = ["README.md", "LICENSE", "provenance.yaml", "parquet/files.parquet"]
    files += [f"raw/{rel}" for rel in ref] + [f"cog/{rel}" for rel in ref]
    total = sum((data / f).stat().st_size for f in files)
    print(f"{a.repo}\n  {len(files)} files, {total / 1e9:.2f} GB")
    if not a.push:
        print("\ndry run. pass --push to upload")
        return 0

    from huggingface_hub import HfApi

    api = HfApi()
    api.create_repo(a.repo, repo_type="dataset", exist_ok=True, private=False)
    api.upload_folder(
        repo_id=a.repo,
        folder_path=str(data),
        repo_type="dataset",
        allow_patterns=files,
    )
    print(f"\npushed to https://huggingface.co/datasets/{a.repo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
