# ContractFit technical case study

## Problem

Small facilities-service contractors must decide quickly whether a government opportunity is
eligible, achievable, and worth pursuing. The relevant facts are distributed across notices,
solicitations, attachments, amendments, and company records. A missed deadline or certification can
invalidate a bid, while a semantic mismatch can waste days of proposal effort. The engineering
problem is therefore not simply document summarization: the system must preserve evidence, separate
hard rules from judgment, isolate customer data, and expose uncertainty to a human.

## Users and workflow

ContractFit targets small and midsize janitorial, HVAC, landscaping, pest-control, electrical,
plumbing, and general facilities contractors. A user records company capabilities and evidence,
imports or uploads an opportunity, waits for durable document processing, reviews requirements and
match explanations, and decides whether to pursue the work. Pursued opportunities become private
compliance workspaces. Amendments are compared without silently changing prior decisions.

The MVP supports both uploaded solicitations and a shared SAM.gov catalog. Catalog records are
public; analyzed attachments, profiles, reviews, matches, and workflow state are owned by the
authenticated organization.

## Architecture

ContractFit is a modular FastAPI monolith with independent worker processes. PostgreSQL stores
domain and workflow data, pgvector supports semantic retrieval, Redis carries durable processing
jobs, and files are stored by content hash. SQLAlchemy persistence records remain separate from
Pydantic domain models behind a store protocol, allowing fast in-memory tests and a production
PostgreSQL adapter. Alembic is the schema-change boundary.

Document processing parses PDF, DOCX, and TXT files into stable page records. Pages with insufficient
embedded text are marked for local Tesseract OCR. Extracted requirements preserve a document ID,
page or section, supporting text, and confidence. Processing jobs are retryable and recover after a
worker restart.

SAM.gov ingestion is a separate typed boundary. It paginates bounded searches, normalizes provider
payloads, sanitizes failures, deduplicates provider records, and stores immutable content-hashed
snapshots only when data change. Attachments requested by an authenticated organization become
private source documents processed by the same document pipeline.

## AI approach

The system deliberately divides deterministic truth from model-assisted judgment.

Deadlines, territory, set-aside compatibility, certifications, capacity, citation alignment, and
organization access are deterministic. A model cannot override those gates. Semantic comparison is
defined behind a small scorer interface. The optional Ollama adapter asks a local model for a
bounded score and reason in JSON; failures fall back to a lexical scorer and expose the fallback
method in the result.

Embedding retrieval is independently configurable. An Ollama embedding provider produces vectors,
while a service hashes source content, reuses matching cached embeddings, stores vectors through an
index protocol, and performs cosine search through pgvector. If embeddings are unavailable, the
existing scoring path remains functional. This design makes optional AI additive rather than a
single point of failure.

The current extraction engine is deterministic. This is an honest product boundary: the repository
does not claim LLM extraction or prompt-injection resistance that it has not implemented. A future
model-backed extractor must retain exact citations, validate structured output, detect ambiguity,
and pass labeled security and quality evaluations before replacing or augmenting current behavior.

## Human review and traceability

Missing mandatory information is unknown, not satisfied. Low-confidence or conflicting fields can
enter an organization-scoped review queue with deterministic priority. Review decisions retain
evidence and audited transitions. A compliance workspace copies immutable source citations while
allowing users to manage coverage, owners, due dates, notes, and company evidence.

Amendment comparison is intentionally conservative. Catalog fields use exact comparison.
Requirements are unchanged only on normalized exact matches; a changed pair is emitted only when
one unmatched old and one unmatched new requirement share a category. Ambiguous groups remain
separate additions and removals. Comparisons never mutate compliance decisions automatically.

## Evaluation strategy

The repository ships a machine-readable quality gate rather than relying on screenshots or
anecdotes. Four synthetic extraction cases evaluate recall, citation validity, eligibility,
structured values, hard gates, and gate-to-citation alignment. Six instruction-text cases confirm
that the deterministic extractor does not invent fields or eligibility from instruction-like text.
Thirty hand-authored ranking cases measure Top-1 accuracy, Recall@3, and mean reciprocal rank.

The baseline reproduced on 2026-11-04 reports all six recorded extraction metrics at `1.0` for both
small extraction corpora. Lexical ranking reports Top-1 `0.3667`, Recall@3 `0.4333`, and MRR
`0.5306`. These values are regression thresholds, not production accuracy. The corpus is synthetic,
small, and not representative enough to support a customer-quality claim.

CI runs linting, strict type checks, unit tests, migration verification, pgvector search, concurrent
PostgreSQL amendment acknowledgement, and the portfolio quality gate. The quality command returns a
nonzero status on metric or local latency regression and uploads a JSON artifact in CI.

## Security and tenant isolation

Authentication establishes user and organization context. Customer-owned resources are resolved
from that context rather than trusting ownership identifiers in requests. Tests cover cross-tenant
profile, document, opportunity, review, and persistence behavior. Production rejects the seeded
signing secret. External-provider errors are sanitized, uploads are bounded and validated, and CSV
cells that could become formulas are escaped.

The remaining security work is explicit: password rate limiting and recovery, broader malicious
file coverage, SSRF review, output-encoding review, and genuine prompt-injection and exfiltration
tests when an LLM is introduced into document extraction.

## Development-agent orchestration

Agent orchestration is used as an engineering control, not marketed as a runtime product feature.
A Codex orchestrator owns scope and integration. A local OpenCode/Qwen worker may receive a bounded
task with explicit files and acceptance criteria in an isolated worktree. A separate read-only
reviewer can report findings. Neither worker nor reviewer replaces deterministic verification or
the orchestrator's final diff review.

This design demonstrates practical orchestration concerns—context ownership, capability limits,
independent review, clean handoffs, and provider privacy—without granting an autonomous agent access
to product truth or customer decisions.

## Tradeoffs

The modular monolith favors rapid iteration and strong transactional boundaries over premature
service decomposition. A dependency-light dashboard exercises the end-to-end workflow but is less
polished than a dedicated frontend. Local Ollama support improves privacy and reproducibility, while
limiting provider comparison and potentially increasing hardware variability. Synthetic data makes
the repository safe and repeatable, but it cannot substitute for representative customer labels.

The deterministic fallback is intentionally weaker than a strong semantic model. Its value is
availability, debuggability, and a measurable baseline—not equivalent quality. Likewise, the broad
500 ms deterministic latency gate catches blocking regressions but is not a hardware-neutral
service-level objective.

## What the project demonstrates

ContractFit demonstrates end-to-end AI product engineering rather than a thin model wrapper:

- Domain modeling and evidence preservation.
- Deterministic rules surrounding probabilistic components.
- Provider interfaces, fallbacks, caching, and structured outputs.
- Durable processing and idempotent external ingestion.
- Multi-tenant authorization and private workflow state.
- Human review for uncertain, high-impact decisions.
- Reproducible evaluation with explicit limitations.
- Development-agent controls that keep model output advisory.

## Next evidence needed

The highest-value next step is a larger, reviewed document corpus and evidence-grounded structured
extraction pipeline. It should measure field precision/recall, citation validity and coverage,
abstention quality, correction rate, latency, and cost. The ranking corpus should grow to at least
100 reviewed cases, followed by lexical, dense, hybrid, and reranking comparisons on the same data.
Operational work should add a hosted environment, traces around model calls, queue and OCR metrics,
and feedback from real contractor workflows. Those results—not additional feature count—would turn
the MVP into credible production evidence.
