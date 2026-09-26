# MNIST CPU baseline

A small PyTorch MLP for testing LabPilot's real experiment pipeline. This is a
quick development experiment, not a competitive benchmark or evidence that
dropout generally improves accuracy.

The configuration exposes dropout, hidden dimension, learning rate, and batch
size. Defaults train for two epochs on 10,000 MNIST training examples and validate
on 2,000 disjoint examples from the same seeded permutation of the training set.
The official test split is not used for hypothesis selection. Two CPU threads and
fixed seeds keep repeated comparisons practical; GPU support is not required.

LabPilot downloads the four raw MNIST archives to its local dataset cache and checks
their MD5 values before staging them into the image build. `download.py` prepares the
torchvision cache from those archives; training containers have no network access.
Training writes `outputs/metrics.json` with schema version 1, validation accuracy,
validation loss, and the effective seed and epoch count. Logs are informational.

From the LabPilot project root:

```bash
labpilot prepare-example .labpilot/baselines/mnist
labpilot run --goal "Does dropout improve validation accuracy?" \
  --executor docker --repo .labpilot/baselines/mnist \
  --max-experiments 2 --max-replans 0 --min-delta 0.001
```

The preparation command copies this template to a **new dedicated Git repository**
and commits it. It refuses an existing destination. Experiment execution then
leaves that baseline checkout and commit unchanged. The default predefined patch
changes only `dropout: 0.0` to `dropout: 0.3`. Use `--patch FILE` for another supplied
unified diff; no patch generation model is involved.

Docker must be running. The first setup downloads Python dependencies and the
checksum-verified dataset on the host, then builds the image. Later builds reuse
cached dependency and dataset layers. Training itself should take seconds to a few
minutes, depending on hardware.
The image has pinned direct Python dependencies; its exact resolved image ID is
recorded for each execution. Transitive dependencies are not fully locked, and
bit-identical training across architectures or library versions is not promised.

After the first LabPilot run builds the image, reuse it explicitly with:

```bash
labpilot run --goal "Dropout comparison" --executor docker \
  --repo .labpilot/baselines/mnist --reuse-image --image labpilot-mnist:phase2 \
  --max-experiments 2 --max-replans 0 --min-delta 0.001
```

Treat baseline repositories, Dockerfiles, images, and supplied patches as trusted
local inputs. The container reduces accidental host access; it is not a guarantee
against hostile code or vulnerabilities in Docker itself.
