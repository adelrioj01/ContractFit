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


def test_dashboard_authenticates_async_processing_polling() -> None:
    dashboard = (
        Path(__file__).parents[1] / "src" / "contractfit" / "static" / "index.html"
    ).read_text(encoding="utf-8")

    assert (
        "authFetch(`/api/processing-jobs/${encodeURIComponent(jobId)}`)" in dashboard
    )


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
