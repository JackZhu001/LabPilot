"""Image preparation only; torchvision validates the cached MNIST files."""

from torchvision.datasets import MNIST

MNIST("/datasets", train=True, download=True)
