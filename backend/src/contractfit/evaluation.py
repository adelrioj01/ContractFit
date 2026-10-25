from typing import Protocol

from pydantic import BaseModel, Field, model_validator

from contractfit.domain import CompanyProfile, EligibilityStatus, SourceDocument
from contractfit.extraction import RequirementExtractor
from contractfit.matching import OpportunityMatcher


class EvaluationCase(BaseModel):
    name: str
    solicitation: str
    expected_categories: list[str]
    expected_eligibility: EligibilityStatus


class EvaluationReport(BaseModel):
    cases: int
    extraction_recall: float = Field(ge=0, le=1)
    citation_validity: float = Field(ge=0, le=1)
    eligibility_accuracy: float = Field(ge=0, le=1)


class RankingCandidate(BaseModel):
    id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class RankingEvaluationCase(BaseModel):
    name: str = Field(min_length=1)
    query: str = Field(min_length=1)
    candidates: list[RankingCandidate] = Field(min_length=2)
    relevant_ids: set[str] = Field(min_length=1)

    @model_validator(mode="after")
    def relevant_candidates_must_exist(self) -> "RankingEvaluationCase":
        candidate_ids = {candidate.id for candidate in self.candidates}
        if not self.relevant_ids <= candidate_ids:
            raise ValueError("every relevant ID must reference a candidate")
        if len(candidate_ids) != len(self.candidates):
            raise ValueError("candidate IDs must be unique within a ranking case")
        return self


class RankingScorer(Protocol):
    @property
    def name(self) -> str: ...

    def score(self, query: str, candidate: str) -> tuple[float, str]: ...


class RankingMetrics(BaseModel):
    scorer: str
    cases: int = Field(ge=0)
    top_1_accuracy: float = Field(ge=0, le=1)
    recall_at_3: float = Field(ge=0, le=1)
    mean_reciprocal_rank: float = Field(ge=0, le=1)


class RankingComparisonReport(BaseModel):
    cases: int = Field(ge=0)
    lexical: RankingMetrics
    embedding: RankingMetrics | None = None
    embedding_available: bool
    embedding_model: str | None = None
    mrr_delta: float | None = None
    note: str | None = None


def evaluate(cases: list[EvaluationCase], profile: CompanyProfile) -> EvaluationReport:
    extractor = RequirementExtractor()
    matcher = OpportunityMatcher()
    expected_total = 0
    extracted_total = 0
    citations = 0
    correct_eligibility = 0
    for index, case in enumerate(cases):
        document = SourceDocument(filename=f"evaluation-{index}.txt", content=case.solicitation)
        opportunity = extractor.extract(document, source_id=f"evaluation-{index}")
        extracted = {requirement.category for requirement in opportunity.requirements}
        expected = set(case.expected_categories)
        expected_total += len(expected)
        extracted_total += len(expected & extracted)
        citations += sum(
            requirement.evidence.supporting_text in document.content
            for requirement in opportunity.requirements
        )
        result = matcher.match(profile, opportunity)
        correct_eligibility += result.eligibility == case.expected_eligibility
    requirement_count = sum(
        len(
            RequirementExtractor()
            .extract(
                SourceDocument(filename=f"citation-{i}.txt", content=case.solicitation),
                source_id=f"citation-{i}",
            )
            .requirements
        )
        for i, case in enumerate(cases)
    )
    return EvaluationReport(
        cases=len(cases),
        extraction_recall=extracted_total / expected_total if expected_total else 1.0,
        citation_validity=citations / requirement_count if requirement_count else 1.0,
        eligibility_accuracy=correct_eligibility / len(cases) if cases else 1.0,
    )


def evaluate_ranking(
    cases: list[RankingEvaluationCase], scorer: RankingScorer
) -> RankingMetrics:
    if not cases:
        return RankingMetrics(
            scorer=scorer.name,
            cases=0,
            top_1_accuracy=1.0,
            recall_at_3=1.0,
            mean_reciprocal_rank=1.0,
        )

    top_1_total = 0.0
    recall_at_3_total = 0.0
    reciprocal_rank_total = 0.0
    for case in cases:
        ranked = sorted(
            case.candidates,
            key=lambda candidate: scorer.score(case.query, candidate.text)[0],
            reverse=True,
        )
        top_1_total += ranked[0].id in case.relevant_ids
        top_three_ids = {candidate.id for candidate in ranked[:3]}
        recall_at_3_total += len(top_three_ids & case.relevant_ids) / len(case.relevant_ids)
        first_relevant_rank = next(
            (
                index
                for index, candidate in enumerate(ranked, start=1)
                if candidate.id in case.relevant_ids
            ),
            None,
        )
        if first_relevant_rank is not None:
            reciprocal_rank_total += 1 / first_relevant_rank

    case_count = len(cases)
    return RankingMetrics(
        scorer=scorer.name,
        cases=case_count,
        top_1_accuracy=round(top_1_total / case_count, 4),
        recall_at_3=round(recall_at_3_total / case_count, 4),
        mean_reciprocal_rank=round(reciprocal_rank_total / case_count, 4),
    )


def compare_rankers(
    cases: list[RankingEvaluationCase],
    lexical_scorer: RankingScorer,
    embedding_scorer: RankingScorer | None = None,
    note: str | None = None,
) -> RankingComparisonReport:
    lexical = evaluate_ranking(cases, lexical_scorer)
    embedding = (
        evaluate_ranking(cases, embedding_scorer) if embedding_scorer is not None else None
    )
    return RankingComparisonReport(
        cases=len(cases),
        lexical=lexical,
        embedding=embedding,
        embedding_available=embedding is not None,
        embedding_model=embedding.scorer if embedding is not None else None,
        mrr_delta=round(embedding.mean_reciprocal_rank - lexical.mean_reciprocal_rank, 4)
        if embedding is not None
        else None,
        note=note,
    )
