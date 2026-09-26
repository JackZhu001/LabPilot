# Phase 9 — FashionMNIST and source-linked evaluation

Phase 9 added FashionMNIST as a second real dataset profile and ran the saved
DeepSeek configuration proposal through the resumable eight-seed evaluator. The
dataset is a drop-in grayscale, 28×28 image set with 60,000 train and 10,000 test
examples; this phase uses only the training split. See the [official dataset
repository](https://github.com/zalandoresearch/fashion-mnist).

## What changed

- MNIST and FashionMNIST now have explicit profiles for dataset identity, pinned
  torchvision version, split procedure, metric, and direction.
- Raw archives are downloaded on the host and checked against the published MD5
  values before being staged into the image. This works with the executor's
  `--network none` training containers.
- The declared dataset metadata travels through execution state, metric metadata,
  provenance, evaluation manifests, reports, and benchmark cohort keys. Dataset
  profiles and reported metric metadata are validated against each other.
- The DeepSeek repository inspector prioritizes the dataset profile alongside the
  training and model files.

## DeepSeek source run

- Research ID: `78bc7826-795f-4500-8a94-7c01cb02f265`.
- Proposal: `CONFIG_ONLY`, dropout `0.2`.
- Seed 42 baseline: `0.8265`; candidate: `0.8210`; decision: `REJECT`.
- Dataset: FashionMNIST `torchvision-0.20.1 train split`; a seeded permutation selects
  10,000 training and 2,000 validation examples. Primary metric: validation accuracy.
- The run and database are stored locally under the ignored `.labpilot/` directory.

## Source-linked multi-seed results

Evaluation ID: `91278a88-5d9a-42aa-89da-8d9aeb2c2d48`. The source hypothesis and plan
were carried into seeds 42–49. All eight paired evaluations completed successfully.

| Seed | Baseline | Dropout 0.2 | Paired change | Decision |
|---:|---:|---:|---:|---|
| 42 | 0.8265 | 0.8210 | -0.0055 | REJECT |
| 43 | 0.8515 | 0.8445 | -0.0070 | REJECT |
| 44 | 0.8290 | 0.8425 | +0.0135 | KEEP |
| 45 | 0.8200 | 0.8190 | -0.0010 | REJECT |
| 46 | 0.8470 | 0.8415 | -0.0055 | REJECT |
| 47 | 0.8465 | 0.8360 | -0.0105 | REJECT |
| 48 | 0.8150 | 0.8275 | +0.0125 | KEEP |
| 49 | 0.8180 | 0.8270 | +0.0090 | KEEP |

Mean paired change was `+0.0006875`; sample standard deviation was `0.009535`; 3/8
seeds reached KEEP. The variability is much larger than the mean, so this run does not
support a reliable improvement claim. Keep FashionMNIST in its own benchmark cohort;
its scores are not directly comparable with MNIST scores.

Phase 9's planned dataset profile, metadata validation, and source-linked evaluation
are complete. Phase 10 should add an image dataset with different dimensions or
channels and a matching model profile.
