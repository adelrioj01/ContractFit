from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from contractfit.database import Base


class OrganizationRecord(Base):
    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class UserAccountRecord(Base):
    __tablename__ = "user_accounts"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OrganizationMembershipRecord(Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (UniqueConstraint("user_id", name="uq_organization_memberships_user_id"),)

    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("user_accounts.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


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
    insurance_coverages: Mapped[list[str]] = mapped_column(JSON)
    contract_preferences: Mapped[list[str]] = mapped_column(JSON)
    past_performance: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    capability_statement: Mapped[str] = mapped_column(Text)


class SemanticEmbeddingRecord(Base):
    __tablename__ = "semantic_embeddings"
    __table_args__ = (
        UniqueConstraint("target", "target_id", "model", name="uq_semantic_embedding_target"),
        Index(
            "ix_semantic_embeddings_vector_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    target: Mapped[str] = mapped_column(String(50), index=True)
    target_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    organization_id: Mapped[UUID | None] = mapped_column(Uuid, index=True)
    model: Mapped[str] = mapped_column(String(255), index=True)
    content_sha256: Mapped[str] = mapped_column(String(64))
    embedding: Mapped[list[float]] = mapped_column(Vector(768).with_variant(JSON, "sqlite"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SourceDocumentRecord(Base):
    __tablename__ = "source_documents"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "sha256",
            name="uq_source_documents_organization_sha256",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sha256: Mapped[str | None] = mapped_column(String(64))
    storage_key: Mapped[str | None] = mapped_column(String(1000))
    content_type: Mapped[str] = mapped_column(String(255), default="text/plain")
    size_bytes: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(50), default="ready", index=True)
    page_count: Mapped[int] = mapped_column(default=1)
    error_message: Mapped[str | None] = mapped_column(Text)
    origin_opportunity_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("opportunities.id", ondelete="SET NULL"), index=True
    )
    origin_url: Mapped[str | None] = mapped_column(String(2000))
    origin_snapshot_sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    pages: Mapped[list["DocumentPageRecord"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    processing_jobs: Mapped[list["ProcessingJobRecord"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentOriginRecord(Base):
    __tablename__ = "document_origins"

    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    opportunity_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("opportunities.id", ondelete="CASCADE"), primary_key=True
    )
    origin_url: Mapped[str] = mapped_column(String(2000), primary_key=True)
    snapshot_sha256: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("source_documents.id", ondelete="CASCADE"), index=True
    )


class DocumentPageRecord(Base):
    __tablename__ = "document_pages"
    __table_args__ = (
        UniqueConstraint("document_id", "page_number", name="uq_document_pages_number"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    document_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("source_documents.id", ondelete="CASCADE"), index=True
    )
    page_number: Mapped[int]
    text: Mapped[str] = mapped_column(Text)
    needs_ocr: Mapped[bool] = mapped_column(default=False)
    document: Mapped[SourceDocumentRecord] = relationship(back_populates="pages")


class ProcessingJobRecord(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    document_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("source_documents.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(50), index=True)
    stage: Mapped[str] = mapped_column(String(50))
    attempts: Mapped[int] = mapped_column(default=0)
    max_attempts: Mapped[int] = mapped_column(default=3)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    document: Mapped[SourceDocumentRecord] = relationship(back_populates="processing_jobs")


class OpportunityRecord(Base):
    __tablename__ = "opportunities"
    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_opportunities_source_identity"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    source: Mapped[str] = mapped_column(String(100))
    source_id: Mapped[str] = mapped_column(String(255))
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
    review_items: Mapped[list["ReviewItemRecord"]] = relationship(back_populates="opportunity")
    sam_snapshots: Mapped[list["SamOpportunitySnapshotRecord"]] = relationship(
        back_populates="opportunity",
        cascade="all, delete-orphan",
        order_by="SamOpportunitySnapshotRecord.observed_at",
    )


class PipelineItemRecord(Base):
    __tablename__ = "pipeline_items"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "opportunity_id",
            name="uq_pipeline_items_organization_opportunity",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    opportunity_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("opportunities.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(50), index=True)
    owner_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("user_accounts.id", ondelete="SET NULL"), index=True
    )
    next_action: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ComplianceItemRecord(Base):
    __tablename__ = "compliance_items"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "requirement_id",
            name="uq_compliance_items_organization_requirement",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    opportunity_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("opportunities.id", ondelete="CASCADE"), index=True
    )
    requirement_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("requirements.id", ondelete="CASCADE"), index=True
    )
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(255))
    priority: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), index=True)
    evidence_document_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("source_documents.id", ondelete="RESTRICT"), index=True
    )
    evidence_page: Mapped[int | None]
    evidence_section: Mapped[str | None] = mapped_column(String(500))
    evidence_supporting_text: Mapped[str] = mapped_column(Text)
    business_evidence: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    owner_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("user_accounts.id", ondelete="SET NULL"), index=True
    )
    due_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AmendmentAcknowledgementRecord(Base):
    __tablename__ = "amendment_acknowledgements"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "opportunity_id",
            "previous_snapshot_id",
            "current_snapshot_id",
            name="uq_amendment_acknowledgements_version_pair",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    opportunity_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("opportunities.id", ondelete="CASCADE"), index=True
    )
    previous_snapshot_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("sam_opportunity_snapshots.id", ondelete="CASCADE"), index=True
    )
    current_snapshot_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("sam_opportunity_snapshots.id", ondelete="CASCADE"), index=True
    )
    selections: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    acknowledged_by_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("user_accounts.id", ondelete="RESTRICT"), index=True
    )
    acknowledged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class OpportunityWatchRecord(Base):
    __tablename__ = "opportunity_watches"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "opportunity_id",
            name="uq_opportunity_watches_organization_opportunity",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    opportunity_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("opportunities.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class OpportunityAlertRecord(Base):
    __tablename__ = "opportunity_alerts"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "dedupe_key",
            name="uq_opportunity_alerts_organization_dedupe",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    opportunity_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("opportunities.id", ondelete="CASCADE"), index=True
    )
    watch_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("opportunity_watches.id", ondelete="CASCADE"), index=True
    )
    alert_type: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(50), index=True)
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    changed_fields: Mapped[dict[str, object]] = mapped_column(JSON)
    dedupe_key: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class NotificationPreferenceRecord(Base):
    __tablename__ = "notification_preferences"

    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    enabled: Mapped[bool] = mapped_column(default=False)
    recipient_email: Mapped[str] = mapped_column(String(320))
    alert_types: Mapped[list[str]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class NotificationDeliveryRecord(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint("organization_id", "alert_id", name="uq_notification_delivery_alert"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    alert_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("opportunity_alerts.id", ondelete="CASCADE"), index=True
    )
    recipient_email: Mapped[str] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SamIngestionRunRecord(Base):
    __tablename__ = "sam_ingestion_runs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    posted_from: Mapped[date] = mapped_column(Date)
    posted_to: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(50), index=True)
    pages_fetched: Mapped[int] = mapped_column(default=0)
    records_fetched: Mapped[int] = mapped_column(default=0)
    created_count: Mapped[int] = mapped_column(default=0)
    updated_count: Mapped[int] = mapped_column(default=0)
    unchanged_count: Mapped[int] = mapped_column(default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)


class SamOpportunitySnapshotRecord(Base):
    __tablename__ = "sam_opportunity_snapshots"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    opportunity_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("opportunities.id", ondelete="CASCADE"), index=True
    )
    content_sha256: Mapped[str] = mapped_column(String(64), index=True)
    normalized_payload: Mapped[dict[str, object]] = mapped_column(JSON)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    opportunity: Mapped[OpportunityRecord] = relationship(back_populates="sam_snapshots")


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


class ReviewItemRecord(Base):
    __tablename__ = "review_items"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "opportunity_id",
            "field_name",
            name="uq_review_items_opportunity_field",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    opportunity_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("opportunities.id", ondelete="SET NULL"), index=True
    )
    field_name: Mapped[str] = mapped_column(String(255))
    extracted_value: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    mandatory: Mapped[bool] = mapped_column(default=False)
    reason: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), index=True)
    corrected_value: Mapped[str | None] = mapped_column(Text)
    reviewer_id: Mapped[UUID | None] = mapped_column(Uuid)
    resolution_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opportunity: Mapped[OpportunityRecord | None] = relationship(back_populates="review_items")
    evidence: Mapped[list["ReviewEvidenceRecord"]] = relationship(
        back_populates="review_item",
        cascade="all, delete-orphan",
        order_by="ReviewEvidenceRecord.position",
    )


class ReviewEvidenceRecord(Base):
    __tablename__ = "review_evidence"

    review_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("review_items.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("source_documents.id", ondelete="RESTRICT")
    )
    page: Mapped[int | None]
    section: Mapped[str | None] = mapped_column(String(255))
    supporting_text: Mapped[str] = mapped_column(Text)
    review_item: Mapped[ReviewItemRecord] = relationship(back_populates="evidence")
