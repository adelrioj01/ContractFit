from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from contractfit.config import get_settings
from contractfit.domain import CompanyProfile, MatchResult, Opportunity, SourceDocument
from contractfit.evaluation import EvaluationCase, EvaluationReport, evaluate
from contractfit.evaluation_dataset import EVALUATION_CASES
from contractfit.extraction import RequirementExtractor
from contractfit.matching import OpportunityMatcher
from contractfit.sample_data import SAMPLE_PROFILE, SAMPLE_SOLICITATION
from contractfit.store import InMemoryStore

router = APIRouter(prefix="/api")
store = InMemoryStore()
extractor = RequirementExtractor()


class ImportTextRequest(BaseModel):
    filename: str = "solicitation.txt"
    source_id: str = Field(default_factory=lambda: str(uuid4()))
    content: str = Field(min_length=20)


def _matcher() -> OpportunityMatcher:
    settings = get_settings()
    if settings.ai_provider == "ollama":
        from contractfit.ai import OllamaSemanticScorer

        return OpportunityMatcher(
            OllamaSemanticScorer(settings.ollama_base_url, settings.ollama_model)
        )
    return OpportunityMatcher()


def seed_demo() -> None:
    store.reset()
    store.save_profile(SAMPLE_PROFILE.model_copy(deep=True))
    document = store.save_document(
        SourceDocument(filename="sample-hvac-solicitation.txt", content=SAMPLE_SOLICITATION)
    )
    store.save_opportunity(extractor.extract(document, source_id="DEMO-HVAC-001"))


@router.post("/demo/reset", status_code=201)
def reset_demo() -> dict[str, int]:
    seed_demo()
    return {"profiles": 1, "opportunities": len(store.opportunities)}


@router.get("/profile", response_model=CompanyProfile)
def get_profile() -> CompanyProfile:
    if store.profile is None:
        raise HTTPException(status_code=404, detail="No contractor profile configured")
    return store.profile


@router.put("/profile", response_model=CompanyProfile)
def put_profile(profile: CompanyProfile) -> CompanyProfile:
    return store.save_profile(profile)


@router.post("/opportunities/import-text", response_model=Opportunity, status_code=201)
def import_text(request: ImportTextRequest) -> Opportunity:
    document = store.save_document(
        SourceDocument(filename=request.filename, content=request.content)
    )
    opportunity = extractor.extract(document, source_id=request.source_id)
    return store.save_opportunity(opportunity)


@router.get("/opportunities", response_model=list[Opportunity])
def list_opportunities() -> list[Opportunity]:
    return list(store.opportunities.values())


@router.get("/matches", response_model=list[MatchResult])
def list_matches() -> list[MatchResult]:
    if store.profile is None:
        raise HTTPException(status_code=409, detail="Create a contractor profile first")
    matcher = _matcher()
    return [matcher.match(store.profile, item) for item in store.opportunities.values()]


@router.get("/evaluation", response_model=EvaluationReport)
def get_evaluation() -> EvaluationReport:
    if store.profile is None:
        raise HTTPException(status_code=409, detail="Create a contractor profile first")
    cases = [EvaluationCase.model_validate(item) for item in EVALUATION_CASES]
    return evaluate(cases, store.profile)
