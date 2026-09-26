# FashionMNIST CPU baseline

A small, deterministic CPU MLP using torchvision's FashionMNIST training split.
The dataset is downloaded during image preparation, then training runs with
`download=False`. A seeded permutation selects 10,000 training examples followed
by 2,000 validation examples. The run records the torchvision dataset version,
split policy, and validation accuracy metric in its manifest and provenance.

Prepare a dedicated baseline repository with:

```bash
labpilot prepare-example .labpilot/baselines/fashion-mnist \
  --source examples/fashion_mnist_baseline
```

Use a separate Docker image tag such as `labpilot-fashion-mnist:phase9` so the
MNIST image and cached data remain unchanged.
