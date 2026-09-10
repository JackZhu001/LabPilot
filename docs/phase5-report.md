# Phase 5 — Scientific Literature Grounding

Phase 5 extends the proven Phase 4/4.1 experiment loop with bounded literature
grounding. The accepted scientific path is now:

```text
research goal
  → repository inspection
  → typed literature query plan
  → arXiv / Semantic Scholar search
  → deterministic paper deduplication
  → source-checked claims
  → explicit evidence relations and synthesis
  → evidence-grounded hypothesis
  → existing plan / patch / HPO / Docker / DecisionEngine loop
```

The experiment architecture and numerical decision policy were not replaced. Each
new expensive stage uses the existing durable `ResearchState` cursor and SQLite
snapshot transaction. Claim extraction advances one paper per checkpoint. Search
responses are cached by provider, normalized query, and result limit; the cache is
an optimization only, while accepted paper metadata remains in `ResearchState`.

## Implementation

- `LiteratureProvider` isolates domain logic from provider APIs.
- `ArxivProvider` normalizes Atom metadata and abstracts.
- `SemanticScholarProvider` normalizes Graph API metadata, works without a key when
  the service permits it, and reads `SEMANTIC_SCHOLAR_API_KEY` when present.
- DOI, arXiv ID, provider external ID, and conservative normalized-title keys drive
  deterministic cross-provider deduplication in that order.
- Query plans allow at most three typed queries. Research budgets separately bound
  accepted queries, papers, claims, LLM calls/tokens, experiments, and HPO trials.
- Claims retain an exact contiguous source span and `source_scope=ABSTRACT`. The
  service checks each proposed span against the retrieved abstract and discards an
  unsupported claim.
- Evidence stores `SUPPORT`, `CONTRADICT`, or `NEUTRAL` explicitly, with confidence,
  summary, applicability notes, paper/claim IDs, source span, and a hypothesis ID
  when linked.
- Evidence synthesis preserves consistent findings, conflicting findings, gaps,
  and conditions instead of collapsing them into a consensus score.
- Grounded hypotheses carry categorized evidence IDs, an evidence confidence, and
  `LITERATURE_GROUNDED`, `PARTIALLY_GROUNDED`, or `REPOSITORY_ONLY` status.
- Deterministic selection accounts for support count, contradiction count,
  evidence confidence, hypothesis confidence, expected impact, cost, duplicates,
  required change type, and remaining budgets.
- Provider failures are recorded in state and isolated. A working provider can
  continue the run; no useful evidence causes an accurate repository/history
  fallback.

## Real bounded validation

Run ID: `e357c92a-3584-4b45-8ade-80ddfc7911c1`

Runtime root:
`.labpilot/phase5-demo-20260909-235146`

Goal:

> Identify a literature-supported lightweight regularization or architecture
> change that may improve MNIST validation accuracy, then validate the hypothesis
> experimentally.

Bounds:

| Resource | Limit | Used |
| --- | ---: | ---: |
| Literature queries | 2 | 2 |
| Accepted papers | 6 | 6 |
| Accepted claims | 12 | 5 |
| Claims per paper | 2 | ≤2 |
| Hypotheses per batch | 3 | 3 |
| Research iterations | 1 | 1 |
| HPO trials | 3 | 3 |
| Experiments including baseline | 4 | 4 |
| LLM calls | 18 | 13 |
| LLM tokens | 180,000 | 23,651 |

DeepSeek planned these searches:

1. `MNIST regularization dropout weight decay validation accuracy`
2. `MNIST MLP architecture activation function ReLU alternatives validation accuracy`

arXiv supplied six accepted papers. Semantic Scholar returned HTTP errors for both
queries during this run; both degraded outcomes were recorded, and arXiv allowed
the workflow to continue. The accepted set included *Do deep nets really need
weight decay and dropout?* (`arXiv:1802.07042v3`), *The Implicit and Explicit
Regularization Effects of Dropout* (`arXiv:2002.12915v3`), and *Searching for
Activation Functions* (`arXiv:1710.05941v2`).

The extractor accepted five abstract-backed claims and the synthesizer produced
five evidence records: two `SUPPORT` and three `NEUTRAL`. It also retained a
conflict between literature questioning weight decay/dropout under sufficient data
augmentation and evidence favoring scheduled weight decay. It explicitly recorded
the gap that none of the retrieved studies directly tested this small MNIST MLP.

The selected hypothesis was:

> Replace ReLU activation with Swish activation in the hidden layer of the MLP and
> tune learning rate and dropout via HPO to improve MNIST validation accuracy.

Its supporting evidence traces to the claim that replacing ReLU with Swish improved
top-1 ImageNet accuracy in two large architectures. Applicability notes preserve
the scale/task mismatch. The hypothesis has `LITERATURE_GROUNDED` status,
`evidence_confidence=0.9`, and one supporting evidence link. The generated patch
changed `nn.ReLU()` to PyTorch's Swish-equivalent `nn.SiLU()` in `model.py`.

The measured results were:

| Run | Learning rate | Dropout | Validation accuracy |
| --- | ---: | ---: | ---: |
| Baseline | existing config | existing config | 0.9255 |
| Trial 0 | 0.0005611516 | 0.50 | 0.9190 |
| Trial 1 | 0.0001698670 | 0.30 | 0.8975 |
| Trial 2 | 0.0046739525 | 0.05 | **0.9420** |

The best absolute improvement was `+0.0165`. The unchanged deterministic
DecisionEngine returned `KEEP` because this exceeded the configured `0.001`
minimum improvement. The run completed with 28 committed revisions. Aggregate LLM
usage was 19,484 input tokens, 4,167 output tokens, 23,651 total tokens, and 61.846
seconds of provider latency.

## Verification

- Offline suite: `237 passed, 9 deselected`.
- Phase 5 focused suite: `16 passed`.
- Docker integration: `5 passed`.
- Live DeepSeek: `2 passed`.
- Live literature: arXiv `1 passed`; Semantic Scholar `1 skipped` because the
  optional API key was not configured.
- Ruff formatting/lint, strict mypy, lockfile validation, and whitespace checks
  passed.

Normal tests block network access. They cover provider normalization, DOI/arXiv/title
deduplication, cache reuse, provider degradation, query limits, source fidelity,
all three evidence relations, conflicting evidence, hypothesis links, no-literature
fallback, budget exhaustion, and a process-boundary checkpoint/resume path that
does not repeat provider or experiment calls.
