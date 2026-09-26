"""Verified host-side dataset cache for network-isolated Docker builds."""

import hashlib
import os
import subprocess
from pathlib import Path

from labpilot.models.execution import DatasetMetadata

_DATASETS = {
    "mnist": (
        "MNIST",
        "https://storage.googleapis.com/cvdf-datasets/mnist/",
        (
            ("train-images-idx3-ubyte.gz", "f68b3c2dcbeaaa9fbdd348bbdeb94873"),
            ("train-labels-idx1-ubyte.gz", "d53e105ee54ea40749a09fcbcd1e9432"),
            ("t10k-images-idx3-ubyte.gz", "9fb629c4189551a2d022fa330f9573f3"),
            ("t10k-labels-idx1-ubyte.gz", "ec29112dd5afa0611ce80d1b7f02629c"),
        ),
    ),
    "fashion_mnist": (
        "FashionMNIST",
        "https://raw.githubusercontent.com/zalandoresearch/fashion-mnist/master/data/fashion/",
        (
            ("train-images-idx3-ubyte.gz", "8d4fb7e6c68d591d4c3dfef9ec88bf0d"),
            ("train-labels-idx1-ubyte.gz", "25c81989df183df01b3e8a0aad5dffbe"),
            ("t10k-images-idx3-ubyte.gz", "bef4ecab320f06d8554ea6380940ec79"),
            ("t10k-labels-idx1-ubyte.gz", "bb300cfdad3c16e7a12a480ee83cd310"),
        ),
    ),
}


def prepare_dataset(metadata: DatasetMetadata, runtime_root: Path) -> Path:
    """Fetch/checksum raw IDX archives on the host; Docker builds need no network."""
    folder, base_url, resources = _DATASETS[metadata.dataset_id]
    dataset_root = runtime_root / "datasets" / folder
    raw = dataset_root / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    for filename, expected in resources:
        target = raw / filename
        if target.is_file() and hashlib.md5(target.read_bytes()).hexdigest() == expected:
            continue
        temporary = target.with_suffix(target.suffix + ".part")
        try:
            result = subprocess.run(
                [
                    "curl",
                    "--location",
                    "--fail",
                    "--silent",
                    "--show-error",
                    "--max-time",
                    "180",
                    base_url + filename,
                    "--output",
                    str(temporary),
                ],
                capture_output=True,
                text=True,
                timeout=190,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f"Could not download dataset file {filename}: {exc}") from exc
        if result.returncode != 0:
            temporary.unlink(missing_ok=True)
            raise RuntimeError(result.stderr.strip() or f"Could not download {filename}")
        with temporary.open("rb") as downloaded:
            digest = hashlib.file_digest(downloaded, "md5").hexdigest()
        if digest != expected:
            temporary.unlink(missing_ok=True)
            raise ValueError(f"Dataset checksum mismatch: {filename}")
        os.replace(temporary, target)
    return dataset_root
