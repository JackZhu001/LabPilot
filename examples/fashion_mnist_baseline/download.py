"""Download the selected dataset during image preparation, not training."""

import json
from pathlib import Path

from torchvision.datasets import MNIST, FashionMNIST

metadata = json.loads(Path("/tmp/dataset.json").read_text())
datasets = {"mnist": MNIST, "fashion_mnist": FashionMNIST}
try:
    dataset_class = datasets[metadata["dataset_id"]]
except KeyError as exc:
    raise ValueError("Unsupported dataset profile") from exc
dataset_class("/datasets", train=True, download=True)
