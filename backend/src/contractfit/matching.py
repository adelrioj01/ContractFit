from datetime import date
from decimal import Decimal, InvalidOperation

import httpx

from contractfit.ai import LexicalSemanticScorer, SemanticScorer
from contractfit.domain import (
    CompanyProfile,
    EligibilityStatus,
    Evidence,
    GateResult,
    MatchResult,
    Opportunity,
)


class OpportunityMatcher:
    def __init__(self, semantic_scorer: SemanticScorer | None = None) -> None:
        self.semantic_scorer = semantic_scorer or LexicalSemanticScorer()

    def match(
        self,
        profile: CompanyProfile,
        opportunity: Opportunity,
        semantic_override: tuple[float, str, str] | None = None,
    ) -> MatchResult:
        gates = [
            self._deadline_gate(opportunity),
            self._location_gate(profile, opportunity),
            self._set_aside_gate(profile, opportunity),
            self._certification_gate(profile, opportunity),
            self._value_gate(profile, opportunity),
            self._past_performance_gate(profile, opportunity),
        ]
        if any(gate.status == EligibilityStatus.INELIGIBLE for gate in gates):
            eligibility = EligibilityStatus.INELIGIBLE
        elif any(gate.status == EligibilityStatus.NEEDS_REVIEW for gate in gates):
            eligibility = EligibilityStatus.NEEDS_REVIEW
        else:
            eligibility = EligibilityStatus.ELIGIBLE

        if semantic_override is not None:
            semantic_score, semantic_reason, method = semantic_override
        else:
            semantic_score, semantic_reason, method = self._semantic_score(profile, opportunity)

        eligible_ratio = sum(g.status == EligibilityStatus.ELIGIBLE for g in gates) / len(gates)
        score = round((semantic_score * 0.65 + eligible_ratio * 0.35) * 100, 1)
        if eligibility == EligibilityStatus.INELIGIBLE:
            score = min(score, 39.0)
        strengths = [g.reason for g in gates if g.status == EligibilityStatus.ELIGIBLE]
        gaps = [g.reason for g in gates if g.status != EligibilityStatus.ELIGIBLE]
        evidence_summary = self._evidence_summary(gates)
        return MatchResult(
            opportunity_id=opportunity.id,
            profile_id=profile.id,
            eligibility=eligibility,
            fit_score=score,
            scoring_method=method,
            gates=gates,
            strengths=strengths,
            gaps=gaps,
            explanation=(
                f"{semantic_reason} Hard-gate result: {eligibility.value}."
                f"{evidence_summary}"
            ),
        )

    @staticmethod
    def _evidence_summary(gates: list[GateResult]) -> str:
        citations = []
        for gate in gates:
            if gate.evidence is None:
                continue
            location = f"document {gate.evidence.document_id}"
            if gate.evidence.page is not None:
                location += f", page {gate.evidence.page}"
            elif gate.evidence.section:
                location += f", {gate.evidence.section}"
            citations.append(
                f'{gate.name} [{location}]: "{gate.evidence.supporting_text}"'
            )
        return f" Evidence: {'; '.join(citations)}" if citations else ""

    def _semantic_score(
        self, profile: CompanyProfile, opportunity: Opportunity
    ) -> tuple[float, str, str]:
        try:
            semantic_score, semantic_reason = self.semantic_scorer.score(
                profile.capability_statement, opportunity.scope
            )
            method = self.semantic_scorer.name
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            fallback = LexicalSemanticScorer()
            semantic_score, semantic_reason = fallback.score(
                profile.capability_statement, opportunity.scope
            )
            method = f"{fallback.name}-after-model-error"
        return semantic_score, semantic_reason, method

    @staticmethod
    def _evidence(
        opportunity: Opportunity, category: str, evaluated_value: object | None
    ) -> Evidence | None:
        if evaluated_value is None:
            return None
        for requirement in opportunity.requirements:
            if requirement.category != category:
                continue
            if OpportunityMatcher._requirement_matches_value(
                category, requirement.description, evaluated_value
            ):
                return requirement.evidence
        return None

    @staticmethod
    def _requirement_matches_value(
        category: str, requirement_value: str, evaluated_value: object
    ) -> bool:
        if category == "value":
            try:
                return Decimal(requirement_value.replace(",", "")) == Decimal(
                    str(evaluated_value)
                )
            except InvalidOperation:
                return False
        expected = (
            evaluated_value.isoformat()
            if isinstance(evaluated_value, date)
            else str(evaluated_value)
        )
        return " ".join(requirement_value.casefold().split()) == " ".join(
            expected.casefold().split()
        )

    def _deadline_gate(self, opportunity: Opportunity) -> GateResult:
        if opportunity.response_deadline is None:
            return GateResult(
                name="deadline",
                status=EligibilityStatus.NEEDS_REVIEW,
                reason="Deadline is unknown.",
            )
        status = (
            EligibilityStatus.ELIGIBLE
            if opportunity.response_deadline >= date.today()
            else EligibilityStatus.INELIGIBLE
        )
        return GateResult(
            name="deadline",
            status=status,
            reason=f"Deadline is {opportunity.response_deadline.isoformat()}.",
            evidence=self._evidence(opportunity, "deadline", opportunity.response_deadline),
        )

    def _location_gate(self, profile: CompanyProfile, opportunity: Opportunity) -> GateResult:
        if not opportunity.place_of_performance:
            return GateResult(
                name="location",
                status=EligibilityStatus.NEEDS_REVIEW,
                reason="Place of performance is unknown.",
            )
        supported = any(
            state.lower() in opportunity.place_of_performance.lower() for state in profile.states
        )
        return GateResult(
            name="location",
            status=EligibilityStatus.ELIGIBLE if supported else EligibilityStatus.INELIGIBLE,
            reason=f"Location {'is' if supported else 'is not'} in the service territory.",
            evidence=self._evidence(opportunity, "location", opportunity.place_of_performance),
        )

    def _set_aside_gate(self, profile: CompanyProfile, opportunity: Opportunity) -> GateResult:
        if not opportunity.set_aside:
            return GateResult(
                name="set_aside",
                status=EligibilityStatus.NEEDS_REVIEW,
                reason="Set-aside is unknown.",
            )
        supported = opportunity.set_aside.lower() in {item.lower() for item in profile.set_asides}
        return GateResult(
            name="set_aside",
            status=EligibilityStatus.ELIGIBLE if supported else EligibilityStatus.INELIGIBLE,
            reason=f"Set-aside {'matches' if supported else 'does not match'} the company profile.",
            evidence=self._evidence(opportunity, "set_aside", opportunity.set_aside),
        )

    def _certification_gate(self, profile: CompanyProfile, opportunity: Opportunity) -> GateResult:
        required = [
            r.description for r in opportunity.requirements if r.category == "certification"
        ]
        if not required:
            return GateResult(
                name="certification",
                status=EligibilityStatus.ELIGIBLE,
                reason="No mandatory certification was found.",
            )
        held = {item.lower() for item in profile.certifications}
        missing = [item for item in required if item.lower() not in held]
        evidenced_certification = missing[0] if missing else required[0]
        return GateResult(
            name="certification",
            status=EligibilityStatus.INELIGIBLE if missing else EligibilityStatus.ELIGIBLE,
            reason=f"Missing certifications: {', '.join(missing)}"
            if missing
            else "All required certifications are present.",
            evidence=self._evidence(
                opportunity, "certification", evidenced_certification
            ),
        )

    def _value_gate(self, profile: CompanyProfile, opportunity: Opportunity) -> GateResult:
        value = opportunity.estimated_value
        if value is None:
            return GateResult(
                name="contract_value",
                status=EligibilityStatus.NEEDS_REVIEW,
                reason="Estimated value is unknown.",
            )
        within_min = (
            profile.minimum_contract_value is None or value >= profile.minimum_contract_value
        )
        within_max = (
            profile.maximum_contract_value is None or value <= profile.maximum_contract_value
        )
        within = within_min and within_max
        return GateResult(
            name="contract_value",
            status=EligibilityStatus.ELIGIBLE if within else EligibilityStatus.INELIGIBLE,
            reason=f"Estimated value ${value:,.0f} {'fits' if within else 'falls outside'} company capacity.",
            evidence=self._evidence(opportunity, "value", value),
        )

    @staticmethod
    def _past_performance_gate(
        profile: CompanyProfile, opportunity: Opportunity
    ) -> GateResult:
        if not profile.past_performance:
            return GateResult(
                name="past_performance",
                status=EligibilityStatus.NEEDS_REVIEW,
                reason="Past performance has not been demonstrated in the company profile.",
            )
        scope_tokens = {
            token.strip(".,:;()[]").casefold()
            for token in opportunity.scope.split()
            if len(token.strip(".,:;()[]")) >= 4
        }
        ranked_projects: list[tuple[int, str]] = []
        for project in profile.past_performance:
            evidence_text = " ".join(
                [project.title, project.description, *project.service_categories]
            )
            project_tokens = {
                token.strip(".,:;()[]").casefold()
                for token in evidence_text.split()
                if len(token.strip(".,:;()[]")) >= 4
            }
            ranked_projects.append((len(scope_tokens & project_tokens), project.title))
        overlap, title = max(ranked_projects)
        if overlap == 0:
            return GateResult(
                name="past_performance",
                status=EligibilityStatus.NEEDS_REVIEW,
                reason="Past projects are recorded, but no directly relevant experience was found.",
            )
        return GateResult(
            name="past_performance",
            status=EligibilityStatus.ELIGIBLE,
            reason=f'Profile project "{title}" supports relevant experience.',
        )
