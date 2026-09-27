# CIFAR-10 CPU baseline

A deterministic two-convolution model for CIFAR-10's 32×32 RGB images. CIFAR-10
contains 50,000 training images and 10,000 test images; each seeded run draws a
10,000-image training subset and a separate 2,000-image validation subset from
the training split. The test split is not used for model selection.

First copy the example into a dedicated Git baseline, then start a source-linked
multi-seed evaluation. The host downloads and verifies the upstream archive before
building the network-isolated Docker image:

```bash
labpilot prepare-example .labpilot/baselines/cifar10 \
  --source examples/cifar10_baseline
labpilot evaluate --goal "Does dropout improve CIFAR-10 validation accuracy?" \
  --seeds 42,43,44 --executor docker --repo .labpilot/baselines/cifar10
```

The compact profile is intended to make reproducible workflow checks practical;
its metrics are not a state-of-the-art CIFAR-10 benchmark.
