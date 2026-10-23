# ContractFit web application

The first document-ingestion workflow currently lives in the FastAPI-served dashboard at `backend/src/contractfit/static/index.html`. Keeping this vertical slice dependency-free makes the API contract and user workflow easy to validate before introducing a separate frontend build.

## Implemented workflow

1. The user selects a PDF, DOCX, or TXT solicitation.
2. The browser sends it as multipart form data to `POST /api/documents/upload` using the `file` field.
3. The interface displays upload progress and remains disabled while the request is active.
4. The API returns document metadata and a durable processing-job identifier.
5. The interface polls the job through parsing, OCR and extraction, then refreshes the opportunity pipeline and match ranking.

The upload control restricts the file picker to supported formats, but the API remains responsible for authoritative content-type, extension, size, and document validation.

## Planned application

The eventual standalone frontend should provide:

1. Company profile onboarding
2. Opportunity dashboard
3. Opportunity details with requirement citations
4. Requirement review queue
5. Watched opportunities and amendment alerts

Recommended implementation: Next.js, TypeScript, a generated API client, and component and accessibility tests. The existing upload workflow should remain the reference behavior when that migration begins.
