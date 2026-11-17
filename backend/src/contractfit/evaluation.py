from collections import Counter
from typing import Protocol

from pydantic import BaseModel, Field, model_validator

from contractfit.domain import CompanyProfile, EligibilityStatus, SourceDocument
from contractfit.extraction import RequirementExtractor
from contractfit.matching import OpportunityMatcher


class ExpectedRequirement(BaseModel):
    category: str = Field(min_length=1)
    value: str = Field(min_length=1)
    supporting_text: str = Field(min_length=1)


class ExpectedGate(BaseModel):
    name: str = Field(min_length=1)
    status: EligibilityStatus
    supporting_text: str | None = None


class EvaluationCase(BaseModel):
    name: str
    solicitation: str
    expected_categories: list[str]
    expected_eligibility: EligibilityStatus
    expected_requirements: list[ExpectedRequirement]
    expected_gates: list[ExpectedGate]

    @model_validator(mode="after")
    def labels_must_be_complete_and_coherent(self) -> "EvaluationCase":
        expected_category_set = set(self.expected_categories)
        requirement_categories = {item.category for item in self.expected_requirements}
        if len(expected_category_set) != len(self.expected_categories):
            raise ValueError("expected categories must be unique")
        if expected_category_set != requirement_categories:
            raise ValueError("expected categories must match requirement labels")
        requirement_labels = [
            (item.category, item.value, item.supporting_text) for item in self.expected_requirements
        ]
        if len(set(requirement_labels)) != len(requirement_labels):
            raise ValueError("expected requirement labels must be unique")
        if any(
            item.supporting_text not in self.solicitation for item in self.expected_requirements
        ):
            raise ValueError("expected requirement citations must occur in the solicitation")
        allowed_gates = {
            "deadline",
            "location",
            "set_aside",
            "certification",
            "contract_value",
            "past_performance",
        }
        gate_names = [item.name for item in self.expected_gates]
        if len(set(gate_names)) != len(gate_names):
            raise ValueError("expected gate names must be unique")
        if set(gate_names) != allowed_gates:
            raise ValueError("expected gate labels must cover every deterministic gate")
        if any(
            item.supporting_text is not None and item.supporting_text not in self.solicitation
            for item in self.expected_gates
        ):
            raise ValueError("expected gate citations must occur in the solicitation")
        return self


class EvaluationReport(BaseModel):
    cases: int
    extraction_recall: float = Field(ge=0, le=1)
    citation_validity: float = Field(ge=0, le=1)
    eligibility_accuracy: float = Field(ge=0, le=1)
    structured_value_accuracy: float = Field(ge=0, le=1)
    gate_accuracy: float = Field(ge=0, le=1)
    gate_citation_alignment: float = Field(ge=0, le=1)


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
    expected_structured_total = 0
    correct_structured_total = 0
    expected_gate_total = 0
    correct_gate_total = 0
    aligned_gate_citations = 0
    for index, case in enumerate(cases):
        document = SourceDocument(
            organization_id=profile.organization_id,
            filename=f"evaluation-{index}.txt",
            content=case.solicitation,
        )
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
        actual_requirements = Counter(
            (
                requirement.category,
                requirement.description,
                requirement.evidence.supporting_text,
            )
            for requirement in opportunity.requirements
        )
        expected_requirements = Counter(
            (item.category, item.value, item.supporting_text) for item in case.expected_requirements
        )
        expected_structured_total += max(actual_requirements.total(), expected_requirements.total())
        correct_structured_total += (actual_requirements & expected_requirements).total()
        gates_by_name = {gate.name: gate for gate in result.gates}
        expected_gate_total += len(case.expected_gates)
        for expected_gate in case.expected_gates:
            actual_gate = gates_by_name.get(expected_gate.name)
            if actual_gate is None:
                continue
            correct_gate_total += actual_gate.status == expected_gate.status
            actual_supporting_text = (
                actual_gate.evidence.supporting_text if actual_gate.evidence is not None else None
            )
            aligned_gate_citations += actual_supporting_text == expected_gate.supporting_text
    requirement_count = sum(
        len(
            RequirementExtractor()
            .extract(
                SourceDocument(
                    organization_id=profile.organization_id,
                    filename=f"citation-{i}.txt",
                    content=case.solicitation,
                ),
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
        structured_value_accuracy=(
            correct_structured_total / expected_structured_total
            if expected_structured_total
            else 1.0
        ),
        gate_accuracy=(correct_gate_total / expected_gate_total if expected_gate_total else 1.0),
        gate_citation_alignment=(
            aligned_gate_citations / expected_gate_total if expected_gate_total else 1.0
        ),
    )


def evaluate_ranking(cases: list[RankingEvaluationCase], scorer: RankingScorer) -> RankingMetrics:
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
    embedding = evaluate_ranking(cases, embedding_scorer) if embedding_scorer is not None else None
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
