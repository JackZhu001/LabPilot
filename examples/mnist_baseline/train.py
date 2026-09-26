"""Deterministic CPU image experiment with a per-seed held-out training split."""

import json
import os
import random
from pathlib import Path

import torch
import yaml
from model import build_model
from torch import nn
from torch.utils.data import DataLoader, Subset
from torchvision.datasets import MNIST, FashionMNIST
from torchvision.transforms import Compose, Normalize, ToTensor


def main() -> None:
    config = yaml.safe_load(Path("config.yaml").read_text())
    dataset_metadata = json.loads(Path("dataset.json").read_text())
    datasets = {
        "mnist": (MNIST, (0.1307,), (0.3081,)),
        "fashion_mnist": (FashionMNIST, (0.2860,), (0.3530,)),
    }
    if dataset_metadata.get("dataset_id") not in datasets:
        raise ValueError("Unsupported dataset profile")
    dataset_class, mean, std = datasets[dataset_metadata["dataset_id"]]
    expected = {
        "seed",
        "epochs",
        "batch_size",
        "learning_rate",
        "hidden_dim",
        "dropout",
        "train_samples",
        "validation_samples",
        "primary_metric",
        "direction",
    }
    if not isinstance(config, dict) or set(config) != expected:
        raise ValueError("Unexpected configuration fields")
    parameters_path = Path("labpilot-parameters.json")
    if parameters_path.is_file():
        overrides = json.loads(parameters_path.read_text())
        allowed = {"learning_rate", "dropout", "hidden_dim", "batch_size", "epochs"}
        if not isinstance(overrides, dict) or not set(overrides) <= allowed:
            raise ValueError("Unsupported parameter overrides")
        config.update(overrides)
    seed = int(os.environ.get("LABPILOT_SEED", config["seed"]))
    for field in ("epochs", "batch_size", "hidden_dim", "train_samples", "validation_samples"):
        if type(config[field]) is not int or config[field] <= 0:
            raise ValueError(f"{field} must be a positive integer")
    if not 0 <= config["dropout"] < 1 or not 0 < config["learning_rate"] < 1:
        raise ValueError("Invalid dropout or learning rate")
    primary_metric = os.environ.get("LABPILOT_METRIC_NAME", config["primary_metric"])
    direction = os.environ.get("LABPILOT_METRIC_DIRECTION", config["direction"])
    supported_objectives = {
        "validation_accuracy": "maximize",
        "validation_loss": "minimize",
    }
    if supported_objectives.get(primary_metric) != direction:
        raise ValueError("Supported objectives are accuracy/maximize and loss/minimize")
    random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(2)
    dataset = dataset_class(
        "/datasets",
        train=True,
        download=True,
        transform=Compose([ToTensor(), Normalize(mean, std)]),
    )
    indices = torch.randperm(len(dataset), generator=torch.Generator().manual_seed(seed)).tolist()
    train_size, val_size = config["train_samples"], config["validation_samples"]
    if train_size + val_size > len(dataset):
        raise ValueError(f"Train and validation subsets exceed {dataset_metadata['name']}")
    train = DataLoader(
        Subset(dataset, indices[:train_size]),
        batch_size=config["batch_size"],
        shuffle=True,
        generator=torch.Generator().manual_seed(seed),
        num_workers=0,
    )
    validation = DataLoader(
        Subset(dataset, indices[train_size : train_size + val_size]), batch_size=256
    )
    model = build_model(config["hidden_dim"], config["dropout"])
    optimizer = torch.optim.Adam(model.parameters(), lr=config["learning_rate"])
    loss_fn = nn.CrossEntropyLoss()
    for epoch in range(config["epochs"]):
        model.train()
        for images, labels in train:
            optimizer.zero_grad(set_to_none=True)
            loss = loss_fn(model(images), labels)
            loss.backward()
            optimizer.step()
        print(f"Completed epoch {epoch + 1}", flush=True)
    model.eval()
    correct, total_loss = 0, 0.0
    with torch.no_grad():
        for images, labels in validation:
            logits = model(images)
            correct += int((logits.argmax(1) == labels).sum())
            total_loss += float(loss_fn(logits, labels)) * len(labels)
    output = Path("outputs")
    output.mkdir(exist_ok=True)
    report = {
        "schema_version": 1,
        "metrics": {
            "validation_accuracy": correct / val_size,
            "validation_loss": total_loss / val_size,
        },
        "metadata": {
            "seed": seed,
            "epochs": config["epochs"],
            "dataset_name": dataset_metadata["name"],
            "dataset_version": dataset_metadata["version"],
            "split_policy": dataset_metadata["split_policy"],
        },
    }
    (output / "metrics.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
