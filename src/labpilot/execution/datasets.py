"""Verified host-side dataset cache for network-isolated Docker builds."""

import hashlib
import os
import shutil
import subprocess
import tarfile
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

_CIFAR10_FILES = (
    ("data_batch_1", "c99cafc152244af753f735de768cd75f"),
    ("data_batch_2", "d4bba439e000b95fd0a9bffe97cbabec"),
    ("data_batch_3", "54ebc095f3ab1f0389bbae665268c751"),
    ("data_batch_4", "634d18415352ddfa80567beed471001a"),
    ("data_batch_5", "482c414d41f54cd18b22e5b47cb7c3cb"),
    ("test_batch", "40351d587109b95175f43aff81a1287e"),
    ("batches.meta", "5ff9c542aee3614f3951f8cda6e48888"),
)


def _md5(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "md5").hexdigest()


def prepare_dataset(metadata: DatasetMetadata, runtime_root: Path) -> Path:
    """Fetch/checksum data on the host; Docker builds need no network."""
    folder = "CIFAR10" if metadata.dataset_id == "cifar10" else _DATASETS[metadata.dataset_id][0]
    dataset_root = runtime_root / "datasets" / folder
    raw = dataset_root / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    if metadata.dataset_id == "cifar10":
        extracted = dataset_root / "cifar-10-batches-py"
        if all(
            (extracted / name).is_file() and _md5(extracted / name) == digest
            for name, digest in _CIFAR10_FILES
        ):
            return dataset_root
        # The archive is byte-for-byte pinned by the upstream/torchvision MD5.
        url = "https://dataset.bj.bcebos.com/cifar/cifar-10-python.tar.gz"
        filename = "cifar-10-python.tar.gz"
        expected = "c58f30108f718f92721af3b95e74349a"
        archive = raw / filename
        if not archive.is_file() or _md5(archive) != expected:
            temporary = archive.with_suffix(".part")
            try:
                result = subprocess.run(
                    [
                        "curl", "--location", "--fail", "--silent", "--show-error",
                        "--max-time", "300", url, "--output", str(temporary),
                    ],
                    capture_output=True, text=True, timeout=310, check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                temporary.unlink(missing_ok=True)
                raise RuntimeError(f"Could not download dataset file {filename}: {exc}") from exc
            if result.returncode:
                temporary.unlink(missing_ok=True)
                raise RuntimeError(result.stderr.strip() or f"Could not download {filename}")
            if _md5(temporary) != expected:
                temporary.unlink(missing_ok=True)
                raise ValueError(f"Dataset checksum mismatch: {filename}")
            os.replace(temporary, archive)
        with tarfile.open(archive, "r:gz") as bundle:
            members = bundle.getmembers()
            target = dataset_root.resolve()
            if any(
                not (member.isfile() or member.isdir())
                or not (target / member.name).resolve().is_relative_to(target)
                for member in members
            ):
                raise ValueError("Dataset archive contains unsafe paths")
            shutil.rmtree(extracted, ignore_errors=True)
            bundle.extractall(dataset_root, members=members)
        archive.unlink()
        return dataset_root

    _, base_url, resources = _DATASETS[metadata.dataset_id]
    for filename, expected in resources:
        target = raw / filename
        if target.is_file() and _md5(target) == expected:
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
        digest = _md5(temporary)
        if digest != expected:
            temporary.unlink(missing_ok=True)
            raise ValueError(f"Dataset checksum mismatch: {filename}")
        os.replace(temporary, target)
    return dataset_root
