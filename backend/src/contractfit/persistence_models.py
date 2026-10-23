from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from contractfit.database import Base


class CompanyProfileRecord(Base):
    __tablename__ = "company_profiles"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    name: Mapped[str] = mapped_column(String(255))
    service_categories: Mapped[list[str]] = mapped_column(JSON)
    states: Mapped[list[str]] = mapped_column(JSON)
    maximum_distance_miles: Mapped[int | None]
    minimum_contract_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    maximum_contract_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    licenses: Mapped[list[str]] = mapped_column(JSON)
    certifications: Mapped[list[str]] = mapped_column(JSON)
    set_asides: Mapped[list[str]] = mapped_column(JSON)
    naics_codes: Mapped[list[str]] = mapped_column(JSON)
    capability_statement: Mapped[str] = mapped_column(Text)


class SourceDocumentRecord(Base):
    __tablename__ = "source_documents"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    filename: Mapped[str] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OpportunityRecord(Base):
    __tablename__ = "opportunities"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    source: Mapped[str] = mapped_column(String(100))
    source_id: Mapped[str] = mapped_column(String(255), unique=True)
    title: Mapped[str] = mapped_column(String(500))
    agency: Mapped[str | None] = mapped_column(String(500))
    response_deadline: Mapped[date | None] = mapped_column(Date)
    place_of_performance: Mapped[str | None] = mapped_column(String(500))
    set_aside: Mapped[str | None] = mapped_column(String(255))
    estimated_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    scope: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(1000))
    document_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("source_documents.id", ondelete="SET NULL")
    )
    requirements: Mapped[list["RequirementRecord"]] = relationship(
        back_populates="opportunity", cascade="all, delete-orphan"
    )


class RequirementRecord(Base):
    __tablename__ = "requirements"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    opportunity_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("opportunities.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(String(100), index=True)
    description: Mapped[str] = mapped_column(Text)
    mandatory: Mapped[bool]
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    evidence_document_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("source_documents.id", ondelete="RESTRICT")
    )
    evidence_page: Mapped[int | None]
    evidence_section: Mapped[str | None] = mapped_column(String(255))
    evidence_supporting_text: Mapped[str] = mapped_column(Text)
    opportunity: Mapped[OpportunityRecord] = relationship(back_populates="requirements")
