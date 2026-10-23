from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from contractfit.config import get_settings
from contractfit.document_parser import DocumentParseError, DocumentParser
from contractfit.domain import (
    CompanyProfile,
    DocumentPage,
    DocumentStatus,
    MatchResult,
    Opportunity,
    SourceDocument,
)
from contractfit.evaluation import EvaluationCase, EvaluationReport, evaluate
from contractfit.evaluation_dataset import EVALUATION_CASES
from contractfit.extraction import RequirementExtractor
from contractfit.file_storage import FileStorageError, LocalFileStorage
from contractfit.matching import OpportunityMatcher
from contractfit.sample_data import SAMPLE_PROFILE, SAMPLE_SOLICITATION
from contractfit.store import ContractFitStore, InMemoryStore

router = APIRouter(prefix="/api")
_store: ContractFitStore = InMemoryStore()
extractor = RequirementExtractor()
document_parser = DocumentParser()


def configure_store(store: ContractFitStore) -> None:
    global _store
    _store = store


def get_store() -> ContractFitStore:
    return _store


class ImportTextRequest(BaseModel):
    filename: str = "solicitation.txt"
    source_id: str = Field(default_factory=lambda: str(uuid4()))
    content: str = Field(min_length=20)


class DocumentUploadResponse(BaseModel):
    document: SourceDocument
    duplicate: bool
    opportunity: Opportunity | None = None


def _matcher() -> OpportunityMatcher:
    settings = get_settings()
    if settings.ai_provider == "ollama":
        from contractfit.ai import OllamaSemanticScorer

        return OpportunityMatcher(
            OllamaSemanticScorer(settings.ollama_base_url, settings.ollama_model)
        )
    return OpportunityMatcher()


def seed_demo() -> None:
    _store.reset()
    _store.save_profile(SAMPLE_PROFILE.model_copy(deep=True))
    document = _store.save_document(
        SourceDocument(filename="sample-hvac-solicitation.txt", content=SAMPLE_SOLICITATION)
    )
    _store.save_opportunity(extractor.extract(document, source_id="DEMO-HVAC-001"))


@router.post("/demo/reset", status_code=201)
def reset_demo() -> dict[str, int]:
    seed_demo()
    return {"profiles": 1, "opportunities": len(_store.list_opportunities())}


@router.get("/profile", response_model=CompanyProfile)
def get_profile() -> CompanyProfile:
    profile = _store.get_profile()
    if profile is None:
        raise HTTPException(status_code=404, detail="No contractor profile configured")
    return profile


@router.put("/profile", response_model=CompanyProfile)
def put_profile(profile: CompanyProfile) -> CompanyProfile:
    return _store.save_profile(profile)


@router.post("/opportunities/import-text", response_model=Opportunity, status_code=201)
def import_text(request: ImportTextRequest) -> Opportunity:
    document = _store.save_document(
        SourceDocument(filename=request.filename, content=request.content)
    )
    opportunity = extractor.extract(document, source_id=request.source_id)
    return _store.save_opportunity(opportunity)


@router.post(
    "/documents/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(file: Annotated[UploadFile, File()]) -> DocumentUploadResponse:
    settings = get_settings()
    filename = file.filename or ""
    content_type = (file.content_type or "").partition(";")[0].strip().lower()
    data = file.file.read(settings.upload_max_bytes + 1)
    file.file.close()
    if len(data) > settings.upload_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {settings.upload_max_bytes}-byte limit",
        )

    try:
        parsed_pages = document_parser.parse(filename, content_type, data)
        stored = LocalFileStorage(
            Path(settings.upload_directory), max_bytes=settings.upload_max_bytes
        ).store(filename, content_type, data)
    except (DocumentParseError, FileStorageError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    existing = _store.find_document_by_sha256(stored.sha256)
    if existing is not None:
        opportunity = next(
            (
                item
                for item in _store.list_opportunities()
                if item.document_id == existing.id
            ),
            None,
        )
        return DocumentUploadResponse(
            document=existing, duplicate=True, opportunity=opportunity
        )

    needs_ocr = any(page.needs_ocr for page in parsed_pages)
    document = _store.save_document(
        SourceDocument(
            filename=stored.original_filename,
            content="\n\n".join(page.text for page in parsed_pages),
            sha256=stored.sha256,
            storage_key=stored.storage_key,
            content_type=stored.content_type,
            size_bytes=stored.size_bytes,
            status=DocumentStatus.NEEDS_OCR if needs_ocr else DocumentStatus.READY,
            page_count=len(parsed_pages),
        )
    )
    pages = _store.save_document_pages(
        [
            DocumentPage(
                document_id=document.id,
                page_number=page.page_number,
                text=page.text,
                needs_ocr=page.needs_ocr,
            )
            for page in parsed_pages
        ]
    )
    opportunity = None
    if any(page.text.strip() for page in pages):
        opportunity = _store.save_opportunity(
            extractor.extract(
                document,
                source_id=f"UPLOAD-{stored.sha256[:12].upper()}",
                pages=pages,
            )
        )
    return DocumentUploadResponse(
        document=document,
        duplicate=stored.duplicate,
        opportunity=opportunity,
    )


@router.get("/documents", response_model=list[SourceDocument])
def list_documents() -> list[SourceDocument]:
    return _store.list_documents()


@router.get("/documents/{document_id}/pages", response_model=list[DocumentPage])
def list_document_pages(document_id: UUID) -> list[DocumentPage]:
    document = next(
        (item for item in _store.list_documents() if item.id == document_id), None
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return _store.list_document_pages(document_id)


@router.get("/opportunities", response_model=list[Opportunity])
def list_opportunities() -> list[Opportunity]:
    return _store.list_opportunities()


@router.get("/matches", response_model=list[MatchResult])
def list_matches() -> list[MatchResult]:
    profile = _store.get_profile()
    if profile is None:
        raise HTTPException(status_code=409, detail="Create a contractor profile first")
    matcher = _matcher()
    return [matcher.match(profile, item) for item in _store.list_opportunities()]


@router.get("/evaluation", response_model=EvaluationReport)
def get_evaluation() -> EvaluationReport:
    profile = _store.get_profile()
    if profile is None:
        raise HTTPException(status_code=409, detail="Create a contractor profile first")
    cases = [EvaluationCase.model_validate(item) for item in EVALUATION_CASES]
    return evaluate(cases, profile)
