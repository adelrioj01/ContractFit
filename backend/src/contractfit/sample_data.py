from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from contractfit.domain import CompanyProfile, Opportunity, PastPerformanceProject


@dataclass(frozen=True)
class SyntheticCompanySeed:
    profile: CompanyProfile
    email: str
    display_name: str
    user_id: UUID

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
    insurance_coverages=["Commercial general liability", "Workers compensation"],
    contract_preferences=["Preventive maintenance", "Federal facilities"],
    past_performance=[
        PastPerformanceProject(
            title="Central Texas public-facility HVAC maintenance",
            client="Regional public facilities authority",
            description=(
                "Preventive HVAC maintenance, emergency repair, filter replacement, "
                "building automation inspection, and service reporting."
            ),
            service_categories=["HVAC", "preventive maintenance"],
            state="Texas",
            contract_value=Decimal(420000),
            reference_available=True,
        )
    ],
    capability_statement=(
        "Commercial HVAC preventive maintenance, filter replacement, emergency repair, "
        "building automation inspection, and service reporting for public facilities."
    ),
)

SYNTHETIC_COMPANY_SEEDS = (
    SyntheticCompanySeed(
        profile=SAMPLE_PROFILE,
        email="demo@contractfit.local",
        display_name="Demo reviewer",
        user_id=UUID("cd665135-9ab0-491e-9b65-707c33e429a4"),
    ),
    SyntheticCompanySeed(
        profile=CompanyProfile(
            id=UUID("5b806148-f4dc-45c4-bd3d-697dc6c1e901"),
            organization_id=UUID("5b806148-f4dc-45c4-bd3d-697dc6c1e902"),
            name="Ozark Civic Cleaning",
            service_categories=["janitorial", "custodial", "floor care"],
            states=["Arkansas", "AR", "Missouri", "MO"],
            maximum_distance_miles=180,
            minimum_contract_value=Decimal(15000),
            maximum_contract_value=Decimal(1200000),
            certifications=["CIMS-aligned operations"],
            set_asides=["Small Business", "WOSB"],
            naics_codes=["561720"],
            insurance_coverages=["Commercial general liability", "Workers compensation"],
            contract_preferences=["Recurring custodial services", "Public buildings"],
            past_performance=[
                PastPerformanceProject(
                    title="Northwest Arkansas municipal custodial program",
                    client="Synthetic municipal client",
                    description="Nightly janitorial service, floor care, consumables, and quality inspections across six public buildings.",
                    service_categories=["janitorial", "custodial", "floor care"],
                    state="Arkansas",
                    contract_value=Decimal(680000),
                    reference_available=True,
                )
            ],
            capability_statement="Multi-site custodial operations, floor care, sanitation, consumable replenishment, and inspection reporting for public buildings.",
        ),
        email="demo+cleaning@contractfit.local",
        display_name="Morgan Lee",
        user_id=UUID("5b806148-f4dc-45c4-bd3d-697dc6c1e903"),
    ),
    SyntheticCompanySeed(
        profile=CompanyProfile(
            id=UUID("b0a4c371-cb8d-49a9-a215-849d5d61a101"),
            organization_id=UUID("b0a4c371-cb8d-49a9-a215-849d5d61a102"),
            name="Prairie Green Grounds",
            service_categories=["landscaping", "grounds maintenance", "irrigation"],
            states=["Texas", "TX", "Oklahoma", "OK"],
            maximum_distance_miles=220,
            minimum_contract_value=Decimal(20000),
            maximum_contract_value=Decimal(900000),
            licenses=["Texas pesticide applicator"],
            certifications=["Irrigation technician"],
            set_asides=["Small Business"],
            naics_codes=["561730"],
            insurance_coverages=["Commercial general liability", "Commercial auto"],
            contract_preferences=["Multi-site grounds maintenance", "Base year plus options"],
            past_performance=[
                PastPerformanceProject(
                    title="Regional campus grounds maintenance",
                    client="Synthetic education client",
                    description="Mowing, pruning, irrigation repair, seasonal planting, and storm cleanup across a 90-acre campus.",
                    service_categories=["landscaping", "grounds maintenance", "irrigation"],
                    state="Oklahoma",
                    contract_value=Decimal(510000),
                    reference_available=True,
                )
            ],
            capability_statement="Commercial landscaping, irrigation maintenance, mowing, pruning, seasonal planting, and storm cleanup for public campuses.",
        ),
        email="demo+grounds@contractfit.local",
        display_name="Avery Brooks",
        user_id=UUID("b0a4c371-cb8d-49a9-a215-849d5d61a103"),
    ),
    SyntheticCompanySeed(
        profile=CompanyProfile(
            id=UUID("167c2196-73b4-4eb8-bd3d-0934f2a7c201"),
            organization_id=UUID("167c2196-73b4-4eb8-bd3d-0934f2a7c202"),
            name="Delta Public Power Services",
            service_categories=["electrical", "lighting", "generator maintenance"],
            states=["Arkansas", "AR", "Tennessee", "TN"],
            maximum_distance_miles=250,
            minimum_contract_value=Decimal(30000),
            maximum_contract_value=Decimal(1500000),
            licenses=["Arkansas electrical contractor"],
            certifications=["NFPA 70E trained workforce"],
            set_asides=["Small Business", "SDVOSB"],
            naics_codes=["238210"],
            insurance_coverages=["Commercial general liability", "Workers compensation", "Umbrella liability"],
            contract_preferences=["Preventive electrical maintenance", "Emergency response"],
            past_performance=[
                PastPerformanceProject(
                    title="County emergency-power maintenance",
                    client="Synthetic county client",
                    description="Generator load-bank testing, transfer-switch inspection, lighting repair, and emergency callout support.",
                    service_categories=["electrical", "generator maintenance", "lighting"],
                    state="Arkansas",
                    contract_value=Decimal(840000),
                    reference_available=True,
                )
            ],
            capability_statement="Licensed commercial electrical maintenance, generator testing, transfer switches, lighting retrofits, and emergency response.",
        ),
        email="demo+electrical@contractfit.local",
        display_name="Jordan Carter",
        user_id=UUID("167c2196-73b4-4eb8-bd3d-0934f2a7c203"),
    ),
    SyntheticCompanySeed(
        profile=CompanyProfile(
            id=UUID("75ff77c5-f148-49c9-a038-46ba32acd301"),
            organization_id=UUID("75ff77c5-f148-49c9-a038-46ba32acd302"),
            name="GulfLine Plumbing & Backflow",
            service_categories=["plumbing", "backflow testing", "water systems"],
            states=["Louisiana", "LA", "Texas", "TX"],
            maximum_distance_miles=160,
            minimum_contract_value=Decimal(10000),
            maximum_contract_value=Decimal(650000),
            licenses=["Louisiana plumbing contractor"],
            certifications=["Backflow prevention tester"],
            set_asides=["Small Business", "HUBZone"],
            naics_codes=["238220"],
            insurance_coverages=["Commercial general liability", "Workers compensation"],
            contract_preferences=["Service contracts", "Backflow compliance"],
            past_performance=[
                PastPerformanceProject(
                    title="Parish facility plumbing compliance",
                    client="Synthetic parish client",
                    description="Backflow testing, fixture repair, drain service, and annual compliance documentation at public facilities.",
                    service_categories=["plumbing", "backflow testing", "water systems"],
                    state="Louisiana",
                    contract_value=Decimal(310000),
                    reference_available=True,
                )
            ],
            capability_statement="Commercial plumbing repair, backflow testing, drain service, fixture replacement, and compliance reporting.",
        ),
        email="demo+plumbing@contractfit.local",
        display_name="Taylor Nguyen",
        user_id=UUID("75ff77c5-f148-49c9-a038-46ba32acd303"),
    ),
)

SYNTHETIC_OPPORTUNITIES = (
    Opportunity(source="synthetic-demo", source_id="SYN-JANITORIAL-001", title="Federal Office Custodial Services", agency="General Services Administration", response_deadline=date(2027, 3, 15), place_of_performance="Little Rock, Arkansas", set_aside="Small Business", estimated_value=Decimal(780000), scope="Nightly janitorial custodial service, floor care, sanitation, consumable replenishment, and inspection reporting for federal office buildings."),
    Opportunity(source="synthetic-demo", source_id="SYN-GROUNDS-001", title="Airfield Grounds and Irrigation Maintenance", agency="Department of the Air Force", response_deadline=date(2027, 4, 2), place_of_performance="Altus, Oklahoma", set_aside="Small Business", estimated_value=Decimal(620000), scope="Grounds maintenance, mowing, pruning, irrigation repair, seasonal planting, and storm cleanup across installation facilities."),
    Opportunity(source="synthetic-demo", source_id="SYN-ELECTRICAL-001", title="Emergency Generator and Electrical Maintenance", agency="Department of Veterans Affairs", response_deadline=date(2027, 2, 28), place_of_performance="Memphis, Tennessee", set_aside="SDVOSB", estimated_value=Decimal(950000), scope="Generator load-bank testing, transfer-switch inspection, electrical preventive maintenance, lighting repair, and emergency response."),
    Opportunity(source="synthetic-demo", source_id="SYN-PLUMBING-001", title="Backflow Testing and Plumbing Repairs", agency="Department of Agriculture", response_deadline=date(2027, 3, 30), place_of_performance="Baton Rouge, Louisiana", set_aside="HUBZone", estimated_value=Decimal(280000), scope="Annual backflow testing, plumbing fixture repair, drain service, water-system maintenance, and compliance documentation."),
    Opportunity(source="synthetic-demo", source_id="SYN-HVAC-001", title="Regional Federal HVAC Preventive Maintenance", agency="General Services Administration", response_deadline=date(2027, 5, 12), place_of_performance="Dallas, Texas", set_aside="Small Business", estimated_value=Decimal(540000), scope="Commercial HVAC preventive maintenance, filter replacement, emergency repair, building automation inspection, and service reporting."),
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

REAL_FEMA_SOURCE_URL = "https://sam.gov/opp/29ba469d073b45d9a934a2577cc0211a/view"

# Public historical notice used as an honest demo acceptance case.
REAL_FEMA_SOLICITATION = """Title: HVAC Maintenance (Denton, TX) — SAM.gov 70FB8026Q00000053
Agency: Department of Homeland Security, Federal Emergency Management Agency
Response deadline: 2026-09-03
Place of performance: Denton, Texas 76208
Set-aside: Small Business
Scope: Single-site seasonal preventive maintenance and operational tune-ups on four Western Shelter CL-ACXE1200 environmental control units. The contractor provides labor, transportation, tools, equipment, materials, and expertise.
Source URL: https://sam.gov/opp/29ba469d073b45d9a934a2577cc0211a/view
"""
