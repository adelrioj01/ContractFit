# ADR 0003: Cache model embeddings in PostgreSQL with pgvector

## Status

Accepted.

## Context

ContractFit needs semantic comparison that scales beyond token overlap without allowing a
model to decide hard eligibility rules. Recomputing every vector on every request is slow and
expensive, and customer capability statements must remain organization-scoped.

## Decision

- Generate 768-dimensional embeddings through a provider interface. The first real provider is
  Ollama's `/api/embed` endpoint using `nomic-embed-text` by default.
- Cache vectors by target, target ID, provider/model name, and SHA-256 of the source text.
- Store vectors in PostgreSQL using pgvector and an HNSW cosine index.
- Keep opportunity embeddings global while profile embeddings carry an organization boundary.
- Use cosine similarity only as the semantic signal. Dates, location, set-asides,
  certifications, and contract value remain deterministic hard gates.
- Fall back to the existing lexical scorer if embedding generation or retrieval fails.

## Consequences

The application can rank large opportunity sets without repeatedly calling the embedding model.
Changing a source text invalidates its cached vector automatically. Models with dimensions other
than 768 require a deliberate schema migration or a separate vector column/table.
