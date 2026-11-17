# Security

## Reporting

Do not open a public issue containing credentials, customer data, exploit details, or private
documents. Use GitHub's private vulnerability-reporting feature when it is enabled for this
repository. If it is unavailable, contact the repository owner privately through the account shown
on the repository. This personal project does not promise a formal response SLA.

## Supported scope

The current branch is the only supported development line. ContractFit is a portfolio MVP, not a
managed production service.

## Trust boundaries

- Uploaded files, solicitation text, SAM.gov content, filenames, URLs, and model output are
  untrusted input.
- Authentication establishes user and organization identity; client-supplied ownership fields are
  never authoritative.
- Public SAM.gov catalog records may be shared, but analyzed attachments, profiles, evidence,
  reviews, and workflow state are organization-owned.
- Models may suggest semantic scores and explanations. They may not override deterministic gates,
  authorize access, or mark compliance satisfied.
- Secrets belong in environment variables and must never enter logs, snapshots, fixtures, or model
  prompts.

## Existing controls

- Argon2 password hashing and signed access tokens.
- Production refusal when the default signing secret is configured.
- File size, extension, and content-type validation.
- Hash-addressed storage and duplicate detection.
- Sanitized external-provider errors.
- Organization-isolation tests at API and persistence boundaries.
- Formula escaping in compliance CSV exports.
- Deterministic fallbacks when optional model providers fail.

## Known gaps

- Password rate limiting, reset, and email verification remain on the roadmap.
- The deterministic instruction-text suite is not an LLM prompt-injection or exfiltration test.
- A public deployment has not yet been penetration tested.
- External URLs and model/document boundaries require continued SSRF, injection, and output-encoding
  testing before production use.
