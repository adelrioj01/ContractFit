# Feature status

This inventory separates verified implementation from experimental or planned behavior. Source and
test links are repository-relative so claims can be audited from the current checkout.

## Implemented and tested

| Capability | Primary implementation | Representative verification |
|---|---|---|
| Authentication and organization identity | `backend/src/contractfit/auth.py`, `api.py` | `test_auth.py`, `test_auth_api.py`, `test_auth_store.py` |
| Contractor profiles and onboarding | `domain.py`, `api.py`, `sql_store.py` | `test_profile_api.py` |
| PDF, DOCX and TXT parsing | `document_parser.py` | `test_document_parser.py` |
| Hash-addressed file storage | `file_storage.py` | `test_file_storage.py` |
| OCR routing | `ocr.py`, `processing.py` | `test_ocr.py`, `test_processing.py` |
| Evidence-linked deterministic extraction | `extraction.py` | `test_extraction.py`, `test_evaluation.py` |
| Durable processing jobs | `job_queue.py`, `worker.py` | `test_job_queue.py`, `test_processing_job_store.py` |
| Deterministic eligibility gates | `matching.py` | `test_matching.py`, `test_synthetic_dataset.py` |
| Human-review queue | `review.py`, `api.py` | `test_review.py`, `test_review_api.py`, `test_review_store.py` |
| Compliance workspace and CSV export | `compliance.py`, `api.py` | `test_compliance_workspace.py` |
| SAM.gov catalog ingestion | `sam_ingestion.py`, `sam_sync.py` | `test_sam_ingestion.py`, `test_sam_sync.py` |
| Private SAM attachment analysis | `sam_attachments.py`, `api.py` | `test_sam_attachments.py`, `test_sam_attachment_api.py` |
| Pipeline, watches and notifications | `pipeline.py`, `watching.py`, `notifications.py` | `test_pipeline_api.py`, `test_watching_api.py`, `test_notifications.py` |
| Deterministic amendment comparison | `amendments.py` | `test_amendments.py`, `test_amendment_workflow.py` |
| Organization-owned relevance feedback | `feedback.py`, `api.py`, `sql_store.py` | `test_feedback_api.py`, `test_feedback_postgres.py`, `test_dashboard_static.py` |
| Quality and ranking evaluation | `quality_cli.py`, `ranking_cli.py`, `evaluation.py` | `test_quality_cli.py`, `test_ranking_cli.py` |
| Tenant-aware persistence | `store.py`, `sql_store.py`, migrations | `test_sql_store.py`, document tenant and auth tests |
| HTTP request tracing | `main.py` request middleware | `test_health.py` trace ID and structured completion log |

## Implemented but experimental

| Capability | Current boundary | Evidence |
|---|---|---|
| Local LLM semantic scoring | Ollama only; model failure falls back to lexical scoring | `ai.py`, `matching.py`, `test_matching.py` |
| Embedding retrieval | Ollama embeddings with pgvector; provider-specific quality is not bundled | `embeddings.py`, `test_embeddings.py`, `test_pgvector_store.py` |
| Email delivery | Audited outbox is implemented; SMTP sending is opt-in | `notifications.py`, `notification_worker.py` |
| Local OCR | Tesseract path exists; performance and accuracy are not broadly benchmarked | `ocr.py`, `test_ocr.py` |

## Partially implemented

- The browser dashboard exercises the product workflow, but it is a dependency-light FastAPI-served
  interface rather than the planned standalone frontend.
- Extraction preserves page-level evidence for the implemented deterministic requirement patterns,
  but there is no provider-neutral LLM extraction pipeline yet.
- Ranking has 30 synthetic cases; the roadmap target is at least 100 reviewed cases.
- Alerts and notification delivery exist, but production deliverability and operational dashboards
  have not been validated.

## Planned

- Excel attachment parsing.
- Password-login rate limiting, password reset, and email verification.
- Larger human-reviewed extraction and ranking corpora.
- Prompt-injection and exfiltration evaluations when a model enters document extraction.
- OCR, queue, network, and model latency/resource budgets.
- Paid-pilot validation.
- Hosted deployment and operational telemetry.

## Explicitly out of scope today

- Autonomous bid/no-bid decisions.
- A runtime multi-agent product.
- Legal, procurement, or compliance advice.
- Claims of production accuracy based on the synthetic regression fixtures.
- Sharing customer-owned documents or evidence across organizations.
