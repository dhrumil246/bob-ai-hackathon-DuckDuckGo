# Industry readiness plan

**Goal:** move YieldGuard from a competition prototype to a system built to the requirements a
semiconductor fab would apply, in time for the state-level round.
**Runway:** 8 weeks from 2 November 2026. Quality over speed.
**The question this answers:** "Is it industry ready?" Judges asked this at our last presentation
and we had no answer.

This document is the shared plan. Change it through pull requests like any other file.

---

## 1. What the industry requires

Collected from SEMI standards material, fab-software vendors and published studies. Most sources
are vendors or commentators: there is no formal standard for AI in fabs, so these are the
requirements the market repeatedly describes, not a certification.

| # | Requirement | Evidence |
|---|---|---|
| R1 | **Standard data formats.** Wafer test results arrive as STDF, inspection defects as KLARF, wafer maps as SEMI E142 XML over GEM. Tool data arrives over SECS/GEM, and increasingly EDA / Interface A (SEMI E164) | [semiengineering: test data formats](https://semiengineering.com/introduction-to-test-data-formats) · [yieldWerx: STDF](https://yieldwerx.com/?p=7332) · [yieldWerx: KLARF](https://yieldwerx.com/?p=7110) · [PDF Solutions: E142](https://www.pdf.com/standards/semi-e142-specification-for-substrate-mapping/) · [SEMI: E142 revision](https://www.semi.org/en/standards-watch-2026-apr/major-revision-underway-for-semi-e142) · [Cimetrix: EDA](https://www.cimetrix.com/InterfaceA) |
| R2 | **On-premise.** Yield and process data are core IP; cloud LLM prompts with recipes or SPC data raise IP and export-control (ITAR/EAR) concerns. Fab-software vendors are building air-gapped LLM infrastructure | [SemiWiki: PDF Solutions](https://semiwiki.com/eda/364906-pdf-solutions-ai-driven-collaboration-smarter-decisions) · [Vectara](https://vectara.com/business/solutions/verticals/semiconductors) · [iFactory](https://ifactoryapp.com/article/on-premise-llm-plant-copilot-air-gapped) |
| R3 | **Security and access control.** SEMI E187/E188 cover fab-equipment cybersecurity. AI agents should be bound by the same role-based access as engineers, with audit trails and human checkpoints | [SEMI: first cybersecurity standards](https://semi.org/en/standards-watch-2022-March/SEMI-publishes-first-cybersecurity-standards) · [PDF Solutions: E187](https://www.pdf.com/standards/semi-e187/) · [Silicon Analysts](https://siliconanalysts.com/analysis/ai-agents-semiconductor-ip-leak-supply-chain-vulnerability) |
| R4 | **Model lifecycle.** Equipment wear, process changes and maintenance events shift data; deployed models need drift monitoring, retraining and versioning | [arXiv 2026: MLOps retraining](https://arxiv.org/html/2605.07752v1) · [CRISP-DM virtual metrology](https://annals-csis.org/Volume_39/drp/pdf/4426.pdf) · [MakinaRocks](https://www.makinarocks.ai/en/use-case/ai-driven-quality-prediction-optimizing-semiconductor-manufacturing/) |
| R5 | **Alarm management.** Fabs suffer alarm fatigue; detectors are judged on false-alarm rate, missed-alarm rate and detection delay together | [PDF Solutions: FDC](https://www.pdf.com/precision-fault-detection-and-classification-fdc) · [Semiengineering: FDC](https://semiengineering.com/new-frontiers-in-fault-detection-and-classification/) · [process-control study](https://skoge.folk.ntnu.no/prost/proceedings/acc11/data/papers/1262.pdf) |
| R6 | **Commonality analysis.** The core fab root-cause method traces failing lots through their genealogy (tools, chambers, time windows) and finds what they share that passing lots do not | [PDF Solutions: analysis-ready FDC](https://www.pdf.com/analysis-ready-fdc-in-the-age-of-ai-and-big-data-semiconductor-manufacturing/) · [yieldWerx](https://yieldwerx.com/?p=2365) |
| R7 | **Traceability.** Every answer traces to its data, its model version and the person who acted on it | [Perforce: trust in GenAI](https://www.perforce.com/webinars/iplm/building-trust-genai-semiconductor-design) |

## 2. Where we stand (2 November 2026)

| | Requirement | Today | Gap | |
|---|---|---|---|---|
| R1 | Data formats | `.npy` and JSON upload behind a validation gate | No STDF, E142 or KLARF import | 🔴 |
| R2 | On-premise | Model inference is local; reasoning calls Gemini in the cloud | Lot evidence leaves the machine on every reasoning call | 🔴 |
| R3 | Security | Append-only JSONL stores for feedback and prior reads | No authentication, no roles, no audit log | 🔴 |
| R4 | Model lifecycle | Checkpoint SHA in `holdout_results.json`; calibration measured (ECE 0.0054) | No model version in API responses, no drift monitoring, no "unknown" class, no promotion gate | 🟠 |
| R5 | Alarm management | Recall, ROC-AUC, false-alarm rate (etch detector 1.3%) | No alarms per chamber-day, no detection delay, no alarm grouping | 🟠 |
| R6 | Commonality analysis | Case retrieval and telemetry | Not implemented | 🟠 |
| R7 | Traceability | Provenance labels, evidence graph, citation checks | No record linking answer, model versions and decision. `/api/chat` serves scripted citations when the tool chain fails (see Phase 0) | 🔴 |
| — | Engineering | 7 test files, mock LLM | No CI for the application, no container, minimal logging | 🟠 |

**Strengths to keep and keep saying:** refusal of invalid input before inference, calibrated vs.
ranked confidence kept separate and labelled, citation enforcement and verification, the
cognitive-forcing step. These answer the trust concerns the research raises.

## 3. Working rules

1. **Additive only.** New behaviour lives in new endpoints, new MCP tools, or behind environment
   flags that default to today's behaviour. Existing response fields are never removed or renamed.
2. **Safety net first.** `tests/contract` records every endpoint's response shape and behaviour.
   A change that alters either must say so in its pull request and regenerate the snapshots on purpose.
3. **Branch → pull request → review → merge.** Nothing is pushed straight to `main`.
4. **Tests run in GitHub Actions only.** No model compute on team laptops. Dataset-scale training
   and evaluation run on Colab notebooks under `src/models/*/colab/`.
5. **Each change ships with tests, a short design note and updated docs.**
6. **Split:** back end (APIs, MCP tools, models) by Dhrumil; matching screens by Heet.

## 4. Phases

Each phase lists its acceptance criteria: the phase is done when every criterion is met and shown
in CI or a notebook.

### Week 1 · Foundation
- `tests/contract`: shape and behaviour snapshots for all 21 endpoints, mock LLM, network blocked,
  stores redirected to a temporary folder.
- `.github/workflows/tests.yml`: contract tests on every push and pull request; a manual
  "update snapshots" run that commits regenerated snapshots to the branch.
- Branch protection on `main` (repo owner): require a pull request and passing checks; block force pushes.
- **Done when:** snapshots of the current `main` behaviour are committed and CI is green.

### Weeks 1–2 · Phase 0: no invented content
- `/api/chat` fallback: when the tool chain fails, say so and return only real tool output. No
  scripted citations, invented documents or fixed confidences. Keep the response format.
  An explicitly flagged and visibly labelled demo script may remain for offline use.
- Remove references to systems we do not connect to (MES registry, SECS/GEM interfaces) from
  responses, or label them as planned integrations.
- Every model-backed response carries `model_versions`: name, version, checkpoint SHA, dataset.
- **Done when:** a test forces the tool chain to fail and finds no citation that is not a real tool
  output; every model-backed endpoint returns `model_versions`.

### Weeks 2–4 · Phase 1: fab data in, fab method out
- STDF wafer-sort import → bin map → validation gate → WaferCNN.
- SEMI E142 XML wafer-map import.
- KLARF defect overlay on the electrical bin map.
- New MCP tool `commonality_analysis`: given lot genealogy, rank tools, chambers and time windows
  over-represented among failing lots, with a statistical test and the counts behind it.
- Sample files: public samples where licences allow; otherwise converted from WM-811K and labelled
  as converted.
- **Done when:** a judge can upload an STDF file and get a classified, validated wafer; the
  commonality tool recovers a planted cause in a synthetic genealogy test.

### Weeks 4–5 · Phase 2: on-premise and secure
- `REASONING_PROVIDER=local`: IBM Granite (open weights) via Ollama or vLLM. Developed and measured
  on Colab; eval score reported against Gemini's 16/18.
- Docker Compose for API, MCP server and web app (local LLM optional).
- Authentication with roles (engineer, reviewer, admin); MCP tools restricted by role.
- Append-only audit log: who asked, input hashes, tools called, model versions, answer, decision.
- **Done when:** the full chain runs with no outbound network call; every investigation produces
  one audit record.

### Weeks 5–7 · Phase 3: model lifecycle
- `models.json` registry and `/api/models`.
- Drift monitor: daily input and prediction distributions against the training baseline.
- "Unknown" for WaferCNN: flag wafers far from anything seen in training (embedding distance),
  route to review. Builds on the Wafer Atlas embeddings.
- Retraining notebook with a promotion gate: a candidate must beat the current model on a frozen
  test set with no class regressing.
- Root-cause calibration from `submit_feedback` once enough confirmed causes exist.
- **Done when:** the test-artifact wafers from the self-training study are flagged "unknown" rather
  than classified at 1.00.

### Week 7 · Phase 4: alarms and operations
- Detector KPIs in fab terms: false alarms per chamber-day, missed-alarm rate, detection delay.
- Alarm grouping: one excursion, one alarm.
- Structured logging, health checks, latency targets.

### Week 8 · Freeze
- No new features. Shadow-mode pilot protocol, model cards, the readiness scorecard for the poster,
  rehearsal.

## 5. Decisions

| Date | Decision |
|---|---|
| 2026-11-02 | Tests run in GitHub Actions only, never on laptops |
| 2026-11-02 | Back end / front end split between Dhrumil and Heet |
| 2026-11-02 | Granite development on Colab (no team GPU) |

## 6. Open items

- Branch protection needs the repo owner (Parva).
- Licences of any STDF / E142 parsing library must be checked before adoption.
