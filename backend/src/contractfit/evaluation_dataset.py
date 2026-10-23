EVALUATION_CASES: list[dict[str, object]] = [
    {
        "name": "eligible HVAC opportunity",
        "solicitation": """Title: HVAC Maintenance
Response deadline: 2027-02-15
Place of performance: Dallas, Texas
Set-aside: Small Business
Required certification: EPA 608
Estimated value: $200,000
Scope: Commercial HVAC preventive maintenance and emergency repair.""",
        "expected_categories": ["deadline", "location", "set_aside", "certification", "value"],
        "expected_eligibility": "eligible",
    },
    {
        "name": "unsupported territory",
        "solicitation": """Title: HVAC Maintenance
Response deadline: 2027-03-20
Place of performance: Miami, Florida
Set-aside: Small Business
Required certification: EPA 608
Estimated value: $180,000
Scope: HVAC maintenance for municipal offices.""",
        "expected_categories": ["deadline", "location", "set_aside", "certification", "value"],
        "expected_eligibility": "ineligible",
    },
    {
        "name": "missing certification",
        "solicitation": """Title: Boiler Operations
Response deadline: 2027-04-10
Place of performance: Austin, Texas
Set-aside: Small Business
Required certification: ASME Boiler Operator
Estimated value: $150,000
Scope: Boiler inspection and plant operations.""",
        "expected_categories": ["deadline", "location", "set_aside", "certification", "value"],
        "expected_eligibility": "ineligible",
    },
]
