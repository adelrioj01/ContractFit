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


def _additional_ranking_case(
    name: str,
    query: str,
    relevant: str,
    distractors: tuple[str, str, str],
) -> dict[str, object]:
    return {
        "name": name,
        "query": query,
        "candidates": [
            {"id": "distractor-1", "text": distractors[0]},
            {"id": "relevant", "text": relevant},
            {"id": "distractor-2", "text": distractors[1]},
            {"id": "distractor-3", "text": distractors[2]},
        ],
        "relevant_ids": ["relevant"],
    }


_COMMON_DISTRACTORS = (
    "Nightly office cleaning and restroom consumable restocking.",
    "Seasonal landscape mowing and irrigation inspection.",
    "Administrative records scanning and document indexing.",
)


RANKING_EVALUATION_CASES.extend(
    [
        _additional_ranking_case(
            "fire alarm life safety",
            "NICET technicians inspect fire alarms, notification devices and life-safety controls.",
            "Testing of detection panels, horns, strobes and emergency signaling systems.",
            _COMMON_DISTRACTORS,
        ),
        _additional_ranking_case(
            "elevator preventive service",
            "Licensed mechanics maintain elevators, lifts and vertical transportation equipment.",
            "Hoist, cab, controller and conveyance preventive maintenance with callout repair.",
            _COMMON_DISTRACTORS,
        ),
        _additional_ranking_case(
            "roof envelope repair",
            "Commercial roof inspection, waterproofing and storm-leak response.",
            "Membrane, flashing and building-envelope repair for water intrusion.",
            _COMMON_DISTRACTORS,
        ),
        _additional_ranking_case(
            "physical security operations",
            "Uniformed guards provide patrol, visitor screening and access control.",
            "Protective security officers staff entrances and conduct facility rounds.",
            _COMMON_DISTRACTORS,
        ),
        _additional_ranking_case(
            "solid waste and recycling",
            "We collect refuse, recycling and bulky waste from institutional sites.",
            "Scheduled trash hauling, container service and recyclable-material recovery.",
            _COMMON_DISTRACTORS,
        ),
        _additional_ranking_case(
            "winter weather response",
            "Snow plowing, ice control and sidewalk deicing for public campuses.",
            "Winter storm response with pavement clearing and anti-icing treatment.",
            _COMMON_DISTRACTORS,
        ),
        _additional_ranking_case(
            "protective coatings",
            "Interior painting, exterior coatings and surface preparation.",
            "Wall and structural finish application with lead-safe preparation.",
            _COMMON_DISTRACTORS,
        ),
        _additional_ranking_case(
            "commercial flooring",
            "Carpet, tile and resilient flooring replacement in occupied buildings.",
            "Floor-covering installation including LVT, sheet goods and carpet systems.",
            _COMMON_DISTRACTORS,
        ),
        _additional_ranking_case(
            "locksmith and door hardware",
            "Locksmiths service master-key systems, locks and door hardware.",
            "Rekeying, cylinder replacement and physical access hardware repair.",
            _COMMON_DISTRACTORS,
        ),
        _additional_ranking_case(
            "standby power systems",
            "Technicians load-test generators and maintain emergency backup power.",
            "Genset inspection, fuel-system service and automatic transfer-switch testing.",
            _COMMON_DISTRACTORS,
        ),
        _additional_ranking_case(
            "commercial kitchen equipment",
            "Repair of institutional ovens, cooking lines and refrigeration equipment.",
            "Food-service appliance maintenance for ranges, walk-ins and dish machines.",
            _COMMON_DISTRACTORS,
        ),
        _additional_ranking_case(
            "aquatic facility operations",
            "Pool operators manage chlorine chemistry, filtration and aquatic safety.",
            "Natatorium water treatment, pump service and swimming-facility operations.",
            _COMMON_DISTRACTORS,
        ),
        _additional_ranking_case(
            "cooling tower water treatment",
            "Water-treatment specialists control scale, corrosion and Legionella risk.",
            "Cooling-tower chemical management, sampling and biological control.",
            _COMMON_DISTRACTORS,
        ),
        _additional_ranking_case(
            "mold remediation",
            "Certified teams remediate mold and moisture damage with containment.",
            "Microbial cleanup, negative-air isolation and damp-material removal.",
            _COMMON_DISTRACTORS,
        ),
        _additional_ranking_case(
            "hazardous material abatement",
            "Licensed crews perform asbestos and lead-paint abatement.",
            "Hazardous building-material removal with regulated containment and disposal.",
            _COMMON_DISTRACTORS,
        ),
        _additional_ranking_case(
            "window and glazing service",
            "Glaziers replace windows, storefront glass and curtain-wall seals.",
            "Architectural glazing repair, insulated glass replacement and resealing.",
            _COMMON_DISTRACTORS,
        ),
        _additional_ranking_case(
            "masonry restoration",
            "Masons repair brick, concrete and deteriorated mortar joints.",
            "Tuckpointing, façade masonry stabilization and cast-concrete patching.",
            _COMMON_DISTRACTORS,
        ),
        _additional_ranking_case(
            "parking pavement maintenance",
            "Parking-lot asphalt repair, sealcoating and traffic striping.",
            "Pavement resurfacing, crack sealing and stall-marking restoration.",
            _COMMON_DISTRACTORS,
        ),
        _additional_ranking_case(
            "fleet maintenance",
            "Mechanics maintain municipal vehicles, light trucks and fleet equipment.",
            "Automotive preventive service, diagnostics and garage repair operations.",
            _COMMON_DISTRACTORS,
        ),
        _additional_ranking_case(
            "institutional laundry",
            "Laundry operations process hospital linens, uniforms and textiles.",
            "Commercial washing, drying, folding and linen distribution service.",
            _COMMON_DISTRACTORS,
        ),
        _additional_ranking_case(
            "loading dock equipment",
            "Technicians repair dock levelers, overhead doors and vehicle restraints.",
            "Loading-bay equipment maintenance for roll-up doors and dock lifts.",
            _COMMON_DISTRACTORS,
        ),
        _additional_ranking_case(
            "water damage restoration",
            "Emergency crews extract flood water and dry damaged facilities.",
            "Rapid water-loss mitigation, structural drying and humidity control.",
            _COMMON_DISTRACTORS,
        ),
    ]
)
