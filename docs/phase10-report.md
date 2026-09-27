# Phase 10: CIFAR-10 RGB profile

Phase 10 adds a 32×32 RGB CIFAR-10 baseline with a small convolutional model,
dataset metadata, and host-side dataset preparation for network-isolated Docker
execution. The archive is checked against the checksum used by TorchVision; the
extracted batch files are checked individually. Training uses only the official
training split, drawing 10,000 training and 2,000 validation images with a
per-seed permutation. CIFAR-10 has 50,000 training and 10,000 test images in
32×32 RGB format ([dataset source](https://www.cs.toronto.edu/~kriz/cifar.html),
[TorchVision loader and checksums](https://github.com/pytorch/vision/blob/main/torchvision/datasets/cifar.py)).
The official test split is not used for model selection.

## Reproducible pilot

Evaluation `7083d63a-6dcc-405a-ab2a-3edae260336b` compared a zero-dropout baseline
against dropout 0.3 across seeds 42, 43, and 44. All six Docker experiments
succeeded and used image `sha256:17937c779d087b40de84c1517dfcf31e1b0e6ae33fb0f5120487b8b8c7c75713`.
The baseline commit was `fd00f0dee380e02fe044a55ae181229e5a8bf994`; each run
used 10,000 training and 2,000 validation examples for two epochs.

| Seed | Baseline accuracy | Dropout 0.3 | Paired change |
| --- | ---: | ---: | ---: |
| 42 | 0.5020 | 0.5030 | +0.0010 |
| 43 | 0.4980 | 0.4775 | −0.0205 |
| 44 | 0.4615 | 0.4890 | +0.0275 |
| **Mean** |  |  | **+0.0027** |
| **Sample standard deviation** |  |  | **0.0240** |

The candidate met the configured KEEP threshold for two of three seeds. The
mean is small relative to seed-to-seed variation, so this pilot does not show a
stable benefit from dropout. It validates the CIFAR-10 execution path and
multi-seed provenance, not model quality. More pre-registered seeds and training
data are needed for a useful performance claim.

An expanded evaluation (`45ed2a90-5a4a-44ff-9f60-fd4f8348401b`) ran the same
baseline commit, Docker image `sha256:c7dd16ec755dd7afe134079eabb659311b925fdc825fa43daab9637a5c132b9c`,
and intervention across seeds 45–52. All 8 runs completed and all 8 rejected
dropout. Mean paired change was −0.0123 (sample standard deviation 0.0126),
with per-run baseline accuracy between 0.4875 and 0.5340. This larger pilot
does not support this dropout setting on this short-training profile; it does
not establish that dropout is generally ineffective.

## Run it

```bash
labpilot prepare-example .labpilot/baselines/cifar10 \
  --source examples/cifar10_baseline
labpilot evaluate \
  --goal "Does dropout improve CIFAR-10 validation accuracy?" \
  --seeds 42,43,44 --executor docker \
  --repo .labpilot/baselines/cifar10 \
  --runtime-root .labpilot/phase10 \
  --db .labpilot/phase10.sqlite3 \
  --image labpilot-cifar10:phase10 --reuse-image --min-delta 0.001
```
