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


RANKING_EVALUATION_CASES: list[dict[str, object]] = [
    {
        "name": "commercial climate-control maintenance",
        "query": "We maintain commercial climate-control systems and provide emergency cooling service.",
        "candidates": [
            {"id": "janitorial", "text": "Nightly office cleaning and consumable restocking."},
            {"id": "hvac", "text": "Preventive heating, ventilation and air-conditioning equipment service."},
            {"id": "roofing", "text": "Commercial roof membrane replacement and leak repair."},
            {"id": "security", "text": "Armed guard and access-control staffing."},
        ],
        "relevant_ids": ["hvac"],
    },
    {
        "name": "healthcare environmental services",
        "query": "Hospital environmental services with infection-control procedures and terminal cleaning.",
        "candidates": [
            {"id": "landscape", "text": "Grounds mowing, pruning and irrigation maintenance."},
            {"id": "electrical", "text": "Switchgear inspection and emergency electrical repair."},
            {"id": "health-cleaning", "text": "Medical-facility sanitation and pathogen disinfection."},
            {"id": "paving", "text": "Parking-lot asphalt resurfacing and striping."},
        ],
        "relevant_ids": ["health-cleaning"],
    },
    {
        "name": "grounds and irrigation",
        "query": "We provide turf care, tree trimming and irrigation repair for public campuses.",
        "candidates": [
            {"id": "plumbing", "text": "Domestic water piping and restroom fixture replacement."},
            {"id": "grounds", "text": "Landscape upkeep, arborist work and sprinkler-system service."},
            {"id": "janitorial", "text": "Day porter and custodial services for public buildings."},
            {"id": "hvac", "text": "Chiller and air-handler preventive maintenance."},
        ],
        "relevant_ids": ["grounds"],
    },
    {
        "name": "integrated pest management",
        "query": "Licensed technicians deliver integrated pest management and rodent exclusion.",
        "candidates": [
            {"id": "waste", "text": "Solid-waste collection and recycling hauling."},
            {"id": "pest", "text": "Insect treatment, vermin control and wildlife exclusion."},
            {"id": "security", "text": "Electronic surveillance monitoring and patrol."},
            {"id": "painting", "text": "Interior painting and wall-covering installation."},
        ],
        "relevant_ids": ["pest"],
    },
    {
        "name": "electrical distribution maintenance",
        "query": "Our electricians service switchgear, panels and emergency power systems.",
        "candidates": [
            {"id": "generator", "text": "Generator testing, breaker inspection and power-distribution repair."},
            {"id": "roof", "text": "Roof inspection and storm-damage repair."},
            {"id": "cleaning", "text": "Industrial floor cleaning and pressure washing."},
            {"id": "landscape", "text": "Seasonal grounds and snow-removal services."},
        ],
        "relevant_ids": ["generator"],
    },
    {
        "name": "commercial plumbing response",
        "query": "Commercial plumbing, drain clearing and backflow-device maintenance.",
        "candidates": [
            {"id": "fire", "text": "Fire-alarm testing and notification appliance inspection."},
            {"id": "water", "text": "Pipe repair, sewer stoppage response and cross-connection testing."},
            {"id": "elevator", "text": "Vertical-transport preventive service and callout repair."},
            {"id": "security", "text": "Badge-reader and intrusion-alarm installation."},
        ],
        "relevant_ids": ["water"],
    },
    {
        "name": "multi-trade facilities operations",
        "query": "We operate public buildings with multi-trade preventive maintenance and work-order dispatch.",
        "candidates": [
            {"id": "fleet", "text": "Vehicle fleet maintenance and parts management."},
            {"id": "facilities", "text": "Integrated building operations, asset upkeep and service-desk coordination."},
            {"id": "catering", "text": "Institutional food preparation and meal delivery."},
            {"id": "records", "text": "Document scanning and records digitization."},
        ],
        "relevant_ids": ["facilities"],
    },
    {
        "name": "boiler plant service",
        "query": "Certified operators inspect boilers, burners and steam-plant controls.",
        "candidates": [
            {"id": "solar", "text": "Photovoltaic array inspection and inverter replacement."},
            {"id": "steam", "text": "Heating-plant operation, combustion tuning and pressure-vessel service."},
            {"id": "janitorial", "text": "Restroom sanitation and common-area cleaning."},
            {"id": "grounds", "text": "Athletic-field and landscape maintenance."},
        ],
        "relevant_ids": ["steam"],
    },
]
