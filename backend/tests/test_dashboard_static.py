from pathlib import Path


def test_dashboard_uses_backend_source_and_status_values() -> None:
    dashboard = (
        Path(__file__).parents[1] / "src" / "contractfit" / "static" / "index.html"
    ).read_text(encoding="utf-8")

    assert '<option value="uploaded_document">Uploaded documents</option>' in dashboard
    assert "needs_review:'Needs review'" in dashboard
    assert "const noGoCount=" in dashboard
    assert '<div class="eyebrow">No-go</div>' in dashboard


def test_dashboard_exposes_persistent_bid_pipeline_controls() -> None:
    dashboard = (
        Path(__file__).parents[1] / "src" / "contractfit" / "static" / "index.html"
    ).read_text(encoding="utf-8")

    assert 'href="#pipeline"' in dashboard
    assert 'data-pipeline-add="${esc(opportunity.id)}"' in dashboard
    assert "authFetch('/api/pipeline/items'" in dashboard
    assert "data-pipeline-item=" in dashboard
    assert "preparing_bid:'Preparing bid'" in dashboard


def test_dashboard_exposes_compliance_workspace_and_source_navigation() -> None:
    dashboard = (
        Path(__file__).parents[1] / "src" / "contractfit" / "static" / "index.html"
    ).read_text(encoding="utf-8")

    assert 'href="#compliance"' in dashboard
    assert 'data-workspace-open="${esc(opportunity.id)}"' in dashboard
    assert "compliance/initialize" in dashboard
    assert "data-compliance-item=" in dashboard
    assert "data-document-page=" in dashboard
    assert "evidenceChanged" in dashboard
    assert "existingEvidence.slice(1)" in dashboard
    assert 'id="export-compliance"' in dashboard
    assert "/compliance/export.csv" in dashboard
    assert "exportComplianceMatrix" in dashboard
    assert 'id="compare-amendments"' in dashboard
    assert "/amendments/compare" in dashboard
    assert "compareAmendments" in dashboard
    assert "item.change_type!=='unchanged'" in dashboard
    assert "data-amendment-selection" in dashboard
    assert "data-apply-amendment" in dashboard
    assert "/amendments/acknowledge" in dashboard


def test_dashboard_exposes_opportunity_monitoring_controls() -> None:
    dashboard = (
        Path(__file__).parents[1] / "src" / "contractfit" / "static" / "index.html"
    ).read_text(encoding="utf-8")
    assert 'href="#alerts"' in dashboard
    assert 'data-watch-action="${watched?' in dashboard
    assert "authFetch('/api/watches')" in dashboard
    assert "authFetch('/api/alerts')" in dashboard
    assert 'data-alert-status="resolved"' in dashboard
    assert 'id="notification-form"' in dashboard
    assert "authFetch('/api/notification-preferences'" in dashboard


def test_dashboard_authenticates_async_processing_polling() -> None:
    dashboard = (
        Path(__file__).parents[1] / "src" / "contractfit" / "static" / "index.html"
    ).read_text(encoding="utf-8")

    assert "authFetch(`/api/processing-jobs/${encodeURIComponent(jobId)}`)" in dashboard


def test_dashboard_exposes_structured_company_onboarding() -> None:
    dashboard = (
        Path(__file__).parents[1] / "src" / "contractfit" / "static" / "index.html"
    ).read_text(encoding="utf-8")

    assert 'href="#profile"' in dashboard
    assert 'id="profile-form"' in dashboard
    assert 'name="insurance_coverages"' in dashboard
    assert 'name="project_description"' in dashboard
    assert "authFetch('/api/profile/completeness')" in dashboard
    assert "authFetch('/api/profile',{method:'PUT'" in dashboard


def test_dashboard_exposes_synthetic_company_switcher_and_disclosure() -> None:
    dashboard = (
        Path(__file__).parents[1] / "src" / "contractfit" / "static" / "index.html"
    ).read_text(encoding="utf-8")

    assert 'id="demo-company"' in dashboard
    assert "demo+cleaning@contractfit.local" in dashboard
    assert "demo+grounds@contractfit.local" in dashboard
    assert "demo+electrical@contractfit.local" in dashboard
    assert "demo+plumbing@contractfit.local" in dashboard
    assert "All demo companies and opportunities are synthetic" in dashboard


def test_dashboard_exposes_accessible_relevance_feedback_controls() -> None:
    dashboard = (
        Path(__file__).parents[1] / "src" / "contractfit" / "static" / "index.html"
    ).read_text(encoding="utf-8")

    assert 'data-feedback-form="${esc(opportunity.id)}"' in dashboard
    assert 'name="rating" value="relevant" required' in dashboard
    assert 'name="rating" value="not_relevant"' in dashboard
    assert 'name="rating" value="unsure"' in dashboard
    assert 'name="reason" maxlength="1000"' in dashboard
    assert 'data-feedback-status role="status" aria-live="polite"' in dashboard
    assert "if(response.status===404){status.textContent='No feedback saved yet.'" in dashboard
    assert "/feedback`,{method:'PUT'" in dashboard
    assert "status.textContent='Saving feedback…'" in dashboard
    assert "status.dataset.kind='error'" in dashboard
    assert "document.querySelector('#matches').addEventListener('submit',saveOpportunityFeedback)" in dashboard
