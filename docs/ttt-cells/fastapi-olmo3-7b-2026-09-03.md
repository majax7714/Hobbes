# TTT cell — fastapi @ `11614be9` · Olmo-3-7B-Instruct · 2026-09-03 (replication of the unseen cell)

**Experiment:** ADR-099. **Why this cell:** the memorised cell was
empty for both 7Bs (the probe put every candidate in unseen or
"neither", C-83), so fastapi — unseen for Olmo 3 at 0.129 — replicates
the unseen result on a repo that is not Hobbes. Every arm is *model +
prompt* under P12. Numbers recorded; the reading is in the hypotheses doc.

## Setup

| | |
|---|---|
| repo, SHA | `fastapi/fastapi` at `11614be9021a` (the DeepSWE base of `fastapi-implicit-head-options` / `fastapi-deprecation-response-headers`), clone `~/.hobbes/deepswe/repos/fastapi` with a venv (`uv venv` + `uv pip install -e .`, C-85) |
| ingest | contained; Python 69.2% capture; 1,206 nodes, 5,262 symbols, 6,672 call edges |
| probe | Olmo 3: files 0.00, definitions 0.00, navigation 0.39 → **0.129, U**; Qwen2.5-Coder-7B: 0.155, neither |
| corpus | recipe v1, hash `bbe5d6a80bb3d2b2`: 27,812 training records (4,696 cards, 23,116 QA), 0 doc chunks (C-82); 566 held-out symbols, 3,262 evaluation records |
| adapter | the pinned recipe, 300 steps, seed 0 — **0.173 epochs** on this corpus; key `8a1bead736d5`, `adapters/allenai-olmo-3-7b-instruct/fastapi/11614be9021a/8a1bead736d5` |
| units | 68 git-history hunks from the 799 commits after the base under `fastapi/`, 3–120 changed lines (mean 26.5), **63 name a file the base graph knows** (C-84); plus the 2 DeepSWE tasks (785 and 943 changed lines, both new files) |

## Gold-diff NLL — 68 git units, paired bootstrap

| arm | mean NLL |
|---|---|
| A0 base, bare | 1.8200 |
| A1 base, aided | 1.8208 |
| A2 adapter, bare | 1.5974 |
| A3 adapter, aided | 1.5951 |

| comparison | population | n | Δ | 95% CI | p | a<b |
|---|---|---|---|---|---|---|
| **A2−A1** | all | 68 | **−0.2234** | [−0.2403, −0.2067] | <0.0002 | 68/68 |
| A2−A0 | all | 68 | −0.2226 | [−0.2421, −0.2037] | <0.0002 | 68/68 |
| A1−A0 | all | 68 | +0.0008 | [−0.0080, +0.0093] | 0.81 | 34/68 |
| A3−A2 | all | 68 | −0.0023 | [−0.0085, +0.0032] | 0.44 | 30/68 |
| A2−A1 | context-known | 63 | −0.2147 | [−0.2317, −0.1982] | <0.0002 | 63/63 |
| A1−A0 | context-known | 63 | −0.0009 | [−0.0099, +0.0074] | 0.84 | 33/63 |

The Hobbes cell's shape, on a foreign repo at half the epochs: the
adapter lowers loss on every unit; the prompted block moves nothing,
alone or on top. No shuffled control was trained here (the Hobbes
control's 74/26 split is not assumed to transfer). Runs
`nll-olmo-fastapi-git-{base,adapter}.json`, `report-olmo-fastapi-git.json`.

*(the two DeepSWE units' NLL is appended when it lands)*
