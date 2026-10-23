from typing import Protocol
from uuid import UUID

from contractfit.domain import CompanyProfile, Opportunity, SourceDocument


class ContractFitStore(Protocol):
    def reset(self) -> None: ...
    def get_profile(self) -> CompanyProfile | None: ...
    def save_profile(self, profile: CompanyProfile) -> CompanyProfile: ...
    def save_document(self, document: SourceDocument) -> SourceDocument: ...
    def save_opportunity(self, opportunity: Opportunity) -> Opportunity: ...
    def list_opportunities(self) -> list[Opportunity]: ...


class InMemoryStore:
    """Replaceable repository for the first vertical slice and local demos."""

    def __init__(self) -> None:
        self.profile: CompanyProfile | None = None
        self.documents: dict[UUID, SourceDocument] = {}
        self.opportunities: dict[UUID, Opportunity] = {}

    def reset(self) -> None:
        self.profile = None
        self.documents.clear()
        self.opportunities.clear()

    def save_profile(self, profile: CompanyProfile) -> CompanyProfile:
        self.profile = profile
        return profile

    def get_profile(self) -> CompanyProfile | None:
        return self.profile

    def save_document(self, document: SourceDocument) -> SourceDocument:
        self.documents[document.id] = document
        return document

    def save_opportunity(self, opportunity: Opportunity) -> Opportunity:
        self.opportunities[opportunity.id] = opportunity
        return opportunity

    def list_opportunities(self) -> list[Opportunity]:
        return list(self.opportunities.values())
