SHIPMENTS = {
    "SHP-2026-001": {
        "origin": "CNSHA",
        "destination": "USLAX",
        "carrier": "Oceanic Freight",
        "current_status": "In Transit",
        "cargo_description": "High-value consumer electronics (Laptops, Smartphones)",
        "bom": [
            {"item_id": "COMP-901", "name": "Lithium-ion Battery Pack", "quantity": 5000},
            {"item_id": "COMP-902", "name": "OLED Display Panel", "quantity": 5000}
        ],
        "inventory_impact": {
            "dependent_production_lines": ["Line-A1 (LA Assembly)", "Line-B2 (LA Assembly)"],
            "buffer_stock_days_remaining": 3
        },
        "penalty_terms": {
            "sla_deadline": "2026-09-12T00:00:00Z",
            "penalty_per_day_late": 50000.00,
            "currency": "USD"
        }
    },
    "SHP-2026-002": {
        "origin": "CNSHA",
        "destination": "USSEA",
        "carrier": "Global Sea Logistics",
        "current_status": "Awaiting Departure",
        "cargo_description": "Plastic toys and novelty items",
        "bom": [
            {"item_id": "TOY-001", "name": "Action Figure Molded Parts", "quantity": 25000},
            {"item_id": "TOY-002", "name": "Packaging Boxes", "quantity": 25000}
        ],
        "inventory_impact": {
            "dependent_production_lines": ["None (Direct to Retail)"],
            "buffer_stock_days_remaining": 14
        },
        "penalty_terms": {
            "sla_deadline": "2026-09-25T00:00:00Z",
            "penalty_per_day_late": 1000.00,
            "currency": "USD"
        }
    },
    "SHP-2026-003": {
        "origin": "CNSZX",
        "destination": "USLAX",
        "carrier": "Pacific Movers",
        "current_status": "In Transit",
        "cargo_description": "Industrial lithium batteries",
        "bom": [
            {"item_id": "BATT-IND-100", "name": "Heavy Duty Battery Cells", "quantity": 1000}
        ],
        "inventory_impact": {
            "dependent_production_lines": ["Line-C (EV Assembly)"],
            "buffer_stock_days_remaining": 2
        },
        "penalty_terms": {
            "sla_deadline": "2026-09-11T00:00:00Z",
            "penalty_per_day_late": 100000.00,
            "currency": "USD"
        }
    },
    "SHP-2026-004": {
        "origin": "NLRTM",
        "destination": "USNYC",
        "carrier": "Trans-Atlantic Shipping",
        "current_status": "In Transit",
        "cargo_description": "High-value automotive transmission parts",
        "bom": [
            {"item_id": "AUTO-TRANS-1", "name": "Transmission Gearbox", "quantity": 300},
            {"item_id": "AUTO-CLUTCH-1", "name": "Clutch Assembly", "quantity": 300}
        ],
        "inventory_impact": {
            "dependent_production_lines": ["Detroit-Main (Auto Assembly)"],
            "buffer_stock_days_remaining": 5
        },
        "penalty_terms": {
            "sla_deadline": "2026-09-18T00:00:00Z",
            "penalty_per_day_late": 25000.00,
            "currency": "USD"
        }
    },
    "SHP-2026-005": {
        "origin": "INBOM",
        "destination": "AEDXB",
        "carrier": "Indian Ocean Lines",
        "current_status": "Customs Cleared",
        "cargo_description": "Cotton textiles and apparel",
        "bom": [
            {"item_id": "TEX-C1", "name": "Cotton Rolls", "quantity": 10000},
            {"item_id": "APP-SHIRT-1", "name": "Finished Shirts", "quantity": 5000}
        ],
        "inventory_impact": {
            "dependent_production_lines": ["Dubai-Retail-Hub"],
            "buffer_stock_days_remaining": 20
        },
        "penalty_terms": {
            "sla_deadline": "2026-09-30T00:00:00Z",
            "penalty_per_day_late": 500.00,
            "currency": "USD"
        }
    },
    "SHP-2026-006": {
        "origin": "DEHAM",
        "destination": "SGSIN",
        "carrier": "EuroAsia Freight",
        "current_status": "In Transit",
        "cargo_description": "Temperature-controlled pharmaceuticals",
        "bom": [
            {"item_id": "PHARMA-VX-1", "name": "Vaccine Vials", "quantity": 50000},
            {"item_id": "PHARMA-RX-2", "name": "Antibiotic Stock", "quantity": 100000}
        ],
        "inventory_impact": {
            "dependent_production_lines": ["SG-Dist-Center"],
            "buffer_stock_days_remaining": 7
        },
        "penalty_terms": {
            "sla_deadline": "2026-09-14T00:00:00Z",
            "penalty_per_day_late": 150000.00,
            "currency": "USD"
        }
    }
}
