"""Small CPU multilayer perceptron with an explicit dropout intervention."""

from torch import nn


def build_model(hidden_dim: int, dropout: float) -> nn.Module:
    return nn.Sequential(
        nn.Flatten(),
        nn.Linear(28 * 28, hidden_dim),
        nn.ReLU(),
        nn.Dropout(dropout),
        nn.Linear(hidden_dim, 10),
    )
