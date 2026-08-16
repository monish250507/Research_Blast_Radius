# Research Blast Radius (RBR)

Evidence-grounded change-impact analysis for computational research.

Given a concrete research change — a Git commit, a commit range, a branch/file diff, or a
file/line region — RBR:

1. **Fingerprints** the repository and builds an *evidence graph* of nodes
   (files, symbols, data artifacts, notebook outputs, config) and deterministic edges
   (imports, definitions, refs, writes, observed runtime edges).
2. **Blast-radius traversal** marks every downstream artifact and documented scientific
   claim that may be affected, along with the exact evidence chain.
3. **Agents** add bounded, auditable semantic judgment (impact mapping, scientific relevance,
   skeptical counter-evidence) **over** the graph — they can never invent graph edges.
4. **Arbiter** (rules R1–R12) enforces provenance, wording, and evidence-existence
   invariants and produces a single auditable `Assessment` with a final status.
5. **Report** renders the impact report with per-conclusion evidence drill-down.

It never claims complete dependency coverage, causal sufficiency, or scientific truth when
the available evidence cannot establish those things. The pipeline is **deterministic and
offline by default** (a no-LLM `stub` provider); a live LLM provider is strictly opt-in.

---

## Safety invariants

- **No evidence → no assertion.** Unknown is treated as *not unaffected*, never as unaffected.
- **Graph edges are created only by deterministic evidence adapters**, never by agents.
- Agents reason over evidence and are bounded by token/schema contracts; their outputs are
  labeled (`INFERRED`, `UNKNOWN`, `OBSERVED`) and cannot fabricate node/edge/evidence IDs.
- Every report conclusion drills down to concrete `evidence_id`s and support spans.
- Causal wording and "sufficient rerun" claims are blocked deterministically by the arbiter.
- **Nothing leaves the process in the default configuration** — repository content is only
  sent to a model provider if the operator explicitly configures one.

---

## Supported scope (V1)

- **Repos:** Python + Git + Jupyter computational research repositories.
- **Change selection:** commit, commit range, branch diff, file diff, file/line region.
- **Evidence adapters:**
  - `python_adapter` — static dependency extraction via `ast`: imports, call sites,
    definitions, file refs; marks dynamic-construct gaps (`UNKNOWN_STATE`).
  - `notebook_adapter` — `nbformat` parsing of cells, inputs/outputs, execution state.
  - `config_adapter` — YAML/JSON/TOML/INI config; output-dir paths are excluded so
    generated results are treated as artifacts, not config.
  - `artifact_adapter` — data/model/figure artifact manifests and content hashes.
  - `git_adapter` — deterministic change extraction between two commits.
- **Storage:** SQLAlchemy (SQLite by default, PostgreSQL via `docker compose` + `.[postgres]`).
- **Agents:** `impact_mapper`, `scientific_analyst`, `skeptic` (stub fallbacks by default).
- **Reports:** Markdown (human) and JSON (machine) with evidence drill-down.

---

## Repository layout

```
pyproject.toml            # packaging, tooling config (ruff/mypy/pytest/coverage gates)
README.md                 # this file
.env.example              # documented configuration template (no secrets)
docker-compose.yml        # optional PostgreSQL service (dev)
scripts/
  bootstrap_fixture.py        # restores golden fixture git history from a bundle
  golden_fixture_repo.bundle  # byte-exact fixture history (see Placeholders)
src/rbr/
  config.py               # pydantic-settings; env prefix RBR_
  logging.py
  agents/                 # provider + 3 agents (all single-shot, schema-bound)
  arbiter/                # rules.py (R1–R12), validator.py (enforcement)
  claims/                 # declared-scientific-claim ingestion + index
  cli/main.py             # init / ingest / analyze / report / status
  evidence/               # ingestion pipeline + deterministic adapters
  graph/                  # builder, contradictions, BFS blast-radius traversal
  orchestrator/analyzer.py# gates + agent pipeline + arbiter assembly
  reports/markdown.py     # auditable impact report renderer
  schemas/                # core.py, graph.py, evidence.py, claims.py,
                          #   agents.py, assessment.py, artifacts.py, golden.py,
                          #   enums.py, ids.py (deterministic ID hashing)
  store/                  # SQLAlchemy models + repository
tests/
  conftest.py             # env + auto-bootstrap of the golden fixture
  harness.py              # repo-agnostic golden scorer
  test_*.py               # golden + unit + adversarial suite (42 tests)
  golden_projects/synthetic_pipeline/
    manifest.toml         # fixture contract (repo_dir, commits, claims file)
    ground_truth.json     # expected status / edges / artifacts / unknowns / contradictions
    repo/                 # synthetic scikit-learn-style fixture (see Placeholders)
infra/
  docker/                 # (empty placeholder — see Placeholders)
  migrations/             # (empty placeholder — see Placeholders)
docs/
  (referenced by earlier versions; not yet written — see Placeholders)
```

---

## Architecture / data flow

```
                      ┌──────────────────────────────┐
 change commits ─────►│  IngestionPipeline           │
 (base..head)         │  git_adapter → file set      │
                      │  python/notebook/config/     │
                      │  artifact adapters           │
                      │  fingerprinting + coverage   │
                      └──────────────┬───────────────┘
                                     │ persist(evidence, nodes, edges, coverage)
                                     ▼
                          ┌─────────────────────┐
                          │  Evidence graph     │   nodes + deterministic edges only
                          └──────────┬──────────┘
                                     │ BFS traversal (downstream_node_ids, gates)
                                     ▼
                ┌───────────────────────────────────────────┐
                │  AnalyzeService (per change)               │
                │  1. gate: impacted subgraph or short-circuit│
                │  2. agents: impact_mapper / scientific_     │
                │     analyst / skeptic (stub or live)        │
                │  3. arbiter R1–R12 → conclusions, unknowns, │
                │     contradictions, validation actions      │
                └──────────────────────────┬──────────────────┘
                                           ▼
                              Assessment (status + audit trail)
                                           ▼
                              report (markdown / JSON drill-down)
```

### Design decisions

- **Blast radius = deterministic BFS over the evidence graph.** The affected set is computed
  from edges created only by adapters; agents contribute semantic judgment, never edges.
- **Final status precedence:** `DISPUTED > AFFECTED > CONDITIONAL > UNKNOWN >
  NOT_EVIDENCED_AFFECTED`. Contradictory evidence never gets averaged away (R6).
- **Unknown is never unaffected (R2).** Any node on the traversal with unknown dependency or
  state stays in the assessment as an `UNKNOWN`; boundary nodes are reported as unknowns, and
  the whole assessment is downgraded from a positive status to `UNKNOWN` if they exist.
- **Deterministic by default.** `RBR_LLM_PROVIDER=stub` yields bounded, evidence-derived
  fallbacks labeled `UNKNOWN`/`INFERRED`; the same code path runs with a live provider.
- **Claims are `CONDITIONAL` but never downgrade the status** when only inferred claim
  mappings are affected.
- **Targeted disputes.** A claim mapping is `DISPUTED` only when its artifact is on the blast
  path of a contradiction (e.g. a notebook-state contradiction).
- **Deterministic ID hashing.** Project/change/assessment/evidence IDs are content-addressed
  hashes (`schemas/ids.py`), so repeated runs on identical input produce identical IDs.

### Arbiter rules (R1–R12)

| Rule | Meaning |
|------|---------|
| R1 | No evidence ID → conclusion rejected. |
| R2 | Unknown dependency ⇒ downstream node cannot be called unaffected. |
| R3 | An OBSERVED runtime edge must be scoped to its run ID. |
| R4 | A STATIC edge cannot be presented as runtime-observed. |
| R5 | An INFERRED claim mapping cannot be presented as direct evidence. |
| R6 | Contradictory evidence → DISPUTED, never averaged. |
| R7 | Missing external version → evidence boundary marked PARTIAL. |
| R8 | Causal wording is blocked. |
| R9 | "Sufficient rerun" wording is blocked. |
| R10 | Any agent-created evidence/artifact ID must exist in the evidence graph. |
| R11 | Inconsistent notebook execution state → state UNKNOWN. |
| R12 | If analysis coverage falls below threshold, report coverage, not confidence. |

---

## Quick start

```bash
# optional: PostgreSQL (sqlite fallback works with zero infrastructure)
docker compose up -d db
pip install -e ".[dev]"

# 1. register a project
rbr init --repo ./path/to/repo --owner you
#   prints: prj:<project_id>

# 2. ingest a change (deterministic fingerprint + evidence graph)
rbr ingest --project <project_id> --repo ./path/to/repo --from <base_sha> --to <head_sha>
#   optionally: --claims claims.yaml  (ingests declared scientific claims)
#   prints: chg:<change_id>

# 3. analyze (traversal + agents + arbiter)
rbr analyze --project <project_id> --change <change_id>
#   prints assessment_id + status + conclusion/unknown/action counts

# 4. report
rbr report --project <project_id> --assessment <assessment_id> --format markdown
rbr report --project <project_id> --assessment <assessment_id> --format json

# 5. status / coverage
rbr status --project <project_id> --change <change_id>
```

The pipeline is offline and deterministic by default (`RBR_LLM_PROVIDER=stub`). With a live
provider configured, the same CLI runs the three agents against the evidence subgraph and the
arbiter still enforces R1–R12 on the results.

### Configuration (`.env` or `RBR_*` environment variables)

See `.env.example`. Highlights:

| Variable | Default | Meaning |
|----------|---------|---------|
| `RBR_DB_URL` | `sqlite+pysqlite:///./rbr_local.db` | storage URL (PostgreSQL: `postgresql+psycopg://…`) |
| `RBR_LLM_PROVIDER` | `stub` | `stub` \| `openai` \| `anthropic` \| `openai_compatible` |
| `RBR_LLM_MODEL` | *(empty)* | model id (e.g. `gpt-4o-mini`) |
| `RBR_LLM_API_KEY` | *(empty)* | API key — never commit a real one |
| `RBR_LLM_BASE_URL` | *(empty)* | base URL for OpenAI-compatible endpoints |
| `RBR_LLM_TEMPERATURE` | `0.0` | sampling temperature |
| `RBR_LOG_LEVEL` | `INFO` | logging level |

---

## Testing / golden benchmark

```bash
pip install -e ".[dev]"
pytest                    # full suite: 42 tests (golden + unit + adversarial)
ruff check src tests      # lint gate
mypy src                  # type gate
pytest --cov=rbr          # coverage gate: fail_under = 70%
```

The golden benchmark is a **plugin slot**. A fixture is any directory
`tests/golden_projects/<name>/` containing:

- `manifest.toml` — `name`, `repo_dir`, `claims_file`, `base_commit`, `change_commit`.
- `ground_truth.json` — `expected_status`, `expected_edges [[source_ref, target_ref, relation]]`,
  `expected_affected_artifact_refs`, `expected_affected_claim_declared_ids`,
  `expected_unknown_refs`, `expected_contradiction_kinds`, `expected_no_impact`, `assert_no_edges`.

`tests/harness.py` runs each fixture through the real pipeline
(ingest → persist → claims → analyze) and scores recall of expected evidence, artifact/claim
coverage, unknown surfacing, contradiction detection, status agreement, and the absence of
forbidden edges — with **zero code changes** when a new fixture is added.

The default fixture is a synthetic scikit-learn-style pipeline. Its git history (two commits:
`d32a15ab…` base, `cc56d9d…` change that bumps `SCALE` in `src/preprocess.py`) is shipped as a
**git bundle** and restored by `tests/conftest.py` automatically on first test run:

```bash
python scripts/bootstrap_fixture.py --check   # verify status (exit 1 if missing)
python scripts/bootstrap_fixture.py --force   # re-create the fixture repo from the bundle
```

The fixture's `.git` is created at test time and **removed when the session ends**, so the
fixture stays a flat, versioned tree (an embedded `.git` would be recorded by git as a
submodule gitlink). If a test run is interrupted, delete
`tests/golden_projects/synthetic_pipeline/repo/.git` before staging the repository.

The fixture's `README.md` deliberately contains prompt-injection text; the adversarial test
asserts it never appears in nodes, edges, locators, assessments, or reports.

---

## Placeholders — what they are and why they exist

This repository intentionally ships with a few stand-ins and one known gap. Each is listed
with the reason it is the way it is.

### 1. The golden fixture repo is synthetic (not a real research repo)

`tests/golden_projects/synthetic_pipeline/repo/` is a hand-built, deterministic stand-in for a
real computational research repository.

**Why it's needed:**
- Tests must be **deterministic, offline, and hermetic** — no network, no licensing concerns,
  no third-party churn breaking the benchmark.
- The fixture exercises every adapter (Python AST, notebook, config, artifacts, git) and every
  interesting outcome (affected artifacts, an affected claim, an unknown notebook-state node,
  a NOTEBOOK_STATE contradiction) in one tiny repo.
- **What to do instead:** drop a real public repo in — add
  `tests/golden_projects/<name>/{manifest.toml, ground_truth.json}` and run the harness.
  No pipeline code changes are required (see *Testing / golden benchmark*).

### 2. Agents run a deterministic `stub` by default

`RBR_LLM_PROVIDER=stub` is the default. Each agent (`impact_mapper`, `scientific_analyst`,
`skeptic`) inherits `BaseAgent` and returns bounded fallback outputs labeled `UNKNOWN` /
`INFERRED` instead of calling a model.

**Why it's needed:**
- Determinism and safety: default installs must not send repository content to a third party,
  cost tokens, or produce nondeterministic results.
- The pipeline, traversal, arbiter, and reports are fully exercised without an API key.
- **What to do instead:** set `RBR_LLM_PROVIDER=openai` (or `openai_compatible` /
  `anthropic`) with an API key; the agents then add semantic judgment on top of the same
  evidence graph, and the arbiter still enforces R1–R12 on their output. The provider layer is
  the deliberate seam for this.

### 3. `docs/` is referenced but not yet written

Earlier READMEs reference `docs/architecture.md`, `docs/evidence-model.md`,
`docs/agent-contracts.md`, and `docs/threat-model.md`. Those files do not exist yet.

**Why:** the documentation effort has so far been consolidated into this README; a separate
docs tree is planned but not a prerequisite for the (working, tested) codebase.

### 4. `infra/docker/` and `infra/migrations/` are empty

`docker-compose.yml` mounts `./infra/migrations` into the Postgres container's initdb; the
directory is currently empty.

**Why:** the default deployment uses SQLite with SQLAlchemy `create_all` and needs no
migrations. The Postgres profile works once migrations/bootstrap SQL is added; until then,
`infra/migrations` is an empty placeholder for that work.

### 5. `anthropic` routes through the OpenAI-compatible client

`agents/provider.py` accepts `anthropic` as a provider name but all non-stub providers
currently share one minimal OpenAI-compatible HTTP client (`OpenAICompatProvider`).

**Why:** a single generic client covers the most common configurations; a native Anthropic
SDK client is a straightforward addition behind the same `AgentProvider` interface.

---

## Known limitations

- Dynamic constructs (e.g. `importlib.import_module("x" + s)`) cannot be resolved statically;
  they surface as `UNKNOWN_STATE` nodes rather than being guessed.
- Claim-affect classification depends on the quality of declared claims and the overlap
  heuristic (`support_span_min_overlap`); precise semantic matching requires a live provider.
- Golden-edge scoring asserts recall and absence of forbidden edges; blanket precision over
  all edges is not asserted because the expected-edge set is intentionally a subset.
- The golden fixture's notebooks lack cell IDs, producing a non-fatal nbformat
  `MissingIDFieldWarning` during validation.
- `infra/migrations` must be populated before the Postgres profile is production-ready.

---

## License

MIT (see `pyproject.toml`). The synthetic golden fixture is included as test data.
