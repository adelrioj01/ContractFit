from pydantic import BaseModel, Field

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
