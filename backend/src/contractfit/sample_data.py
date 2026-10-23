from decimal import Decimal
from uuid import UUID

from contractfit.domain import CompanyProfile

SAMPLE_PROFILE = CompanyProfile(
    id=UUID("9b6720dd-c2fa-4e08-bb21-68ccbc34a1b1"),
    organization_id=UUID("cc1f0326-ed75-4ac0-86ed-2bdf8dc1b613"),
    name="Lone Star Facility Services",
    service_categories=["HVAC", "preventive maintenance", "building maintenance"],
    states=["Texas", "TX"],
    minimum_contract_value=Decimal(25000),
    maximum_contract_value=Decimal(750000),
    licenses=["Texas HVAC Contractor"],
    certifications=["EPA 608"],
    set_asides=["Small Business"],
    naics_codes=["238220", "561210"],
    capability_statement=(
        "Commercial HVAC preventive maintenance, filter replacement, emergency repair, "
        "building automation inspection, and service reporting for public facilities."
    ),
)

SAMPLE_SOLICITATION = """Title: HVAC Preventive Maintenance - Austin Federal Annex
Agency: General Services Administration
Response deadline: 2027-01-15
Place of performance: Austin, Texas
Set-aside: Small Business
Required certification: EPA 608
Estimated value: $240,000
Scope: Quarterly commercial HVAC preventive maintenance, filter replacement, emergency repair, and service reporting for a federal office building.
"""
