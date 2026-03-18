"""
Hardcoded configuration for the Clothing Industry Pre-MVP Synthetic Data Generator.
Change `scenario` to "summer" or "winter" to switch demand profiles.
"""

CONFIG = {
    # ── Run identity ───────────────────────────────────────────────────────────
    "run_id": "CLOTH01",
    "seed": 42,

    # ── Scenario ───────────────────────────────────────────────────────────────
    # "summer" : start April 1  – summer items peak, outerwear near-zero
    # "winter" : start October 1 – outerwear/footwear peak, formalwear holiday spike
    "scenario": "summer",

    # Story overlays on top of baseline demand/supply behavior.
    # Values: "none", "potato_chips_story", "blue_jeans_story"
    "scenario_pack": "potato_chips_story",
    "simulation_engine": "chips_only",
    "prompt_initial_stock": True,
    "initial_stock_dc": 0,
    "initial_stock_stores": {},

    # ── Scale ──────────────────────────────────────────────────────────────────
    "store_count": 2,
    "dc_count": 1,
    "item_count": 1,
    "supplier_count": 3,

    # ── History horizon ────────────────────────────────────────────────────────
    # Derived from scenario in run.py; 4 weeks = 28 days
    "history_weeks": 4,

    # ── Currency ───────────────────────────────────────────────────────────────
    "base_currency": "USD",

    # ── Velocity mix (must sum to item_count) ─────────────────────────────────
    # fast=2, medium=2, slow=1, lumpy=0  (5 total)
    "velocity_mix": {
        "fast":   2,
        "medium": 2,
        "slow":   1,
        "lumpy":  0,
    },

    # ── Clothing categories and item distribution ──────────────────────────────
    # (category, count, velocity, seasonal_profile)
    "categories": [
        {"code": "BASICS",     "description": "Basics & Essentials", "count": 2, "velocity": "fast",   "seasonal": "flat"},
        {"code": "TOPS",       "description": "Tops & T-Shirts",      "count": 2, "velocity": "medium", "seasonal": "summer"},
        {"code": "BOTTOMS",    "description": "Bottoms & Trousers",   "count": 1, "velocity": "slow",   "seasonal": "mild"},
        {"code": "FOOTWEAR",   "description": "Footwear",             "count": 0, "velocity": "slow",   "seasonal": "winter"},
        {"code": "OUTERWEAR",  "description": "Outerwear & Coats",    "count": 0, "velocity": "slow",   "seasonal": "strongwinter"},
        {"code": "ACCESSORIES","description": "Accessories",          "count": 0, "velocity": "lumpy",  "seasonal": "holiday"},
        {"code": "FORMALWEAR", "description": "Formalwear",           "count": 0, "velocity": "lumpy",  "seasonal": "formalholiday"},
    ],

    # Optional explicit catalog for narrative scenarios.
    # When provided, master-data generation uses these items in this exact order.
    "story_items": [
        {
            "code": "ITM_CHIPS_8OZ",
            "description": "Potato Chips 8oz",
            "category": "BASICS",
            "velocity": "fast",
            "seasonal": "flat",
            "size": "One Size",
            "size_type": "Pack",
            "style": "SNK_001",
            "color": "Yellow",
            "story_key": "chips",
        },
    ],

    # ── Departments (ItemMasterGroup1) ─────────────────────────────────────────
    "departments": {
        "MENS":    "Mens",
        "WOMENS":  "Womens",
        "KIDS":    "Kids",
    },

    # ── Price ranges by category (cost_pct = cost as % of selling price) ──────
    "price_ranges": {
        "BASICS":      {"min": 8,   "max": 25,  "cost_pct": 0.40},
        "TOPS":        {"min": 20,  "max": 80,  "cost_pct": 0.38},
        "BOTTOMS":     {"min": 30,  "max": 100, "cost_pct": 0.40},
        "FOOTWEAR":    {"min": 40,  "max": 150, "cost_pct": 0.42},
        "OUTERWEAR":   {"min": 80,  "max": 300, "cost_pct": 0.45},
        "ACCESSORIES": {"min": 10,  "max": 60,  "cost_pct": 0.35},
        "FORMALWEAR":  {"min": 100, "max": 400, "cost_pct": 0.43},
    },

    # ── Base daily demand levels by velocity (units per store per day) ─────────
    "base_demand": {
        "fast":   {"min": 5,  "max": 15},
        "medium": {"min": 2,  "max": 8},
        "slow":   {"min": 0,  "max": 3},
        "lumpy":  {"min": 0,  "max": 1},   # Most days 0; spikes applied separately
    },

    # ── Seasonal demand multipliers by profile and scenario ───────────────────
    # peak_weeks: ISO week numbers (1-52) where the multiplier applies
    # multiplier: demand factor during peak weeks
    # off_multiplier: demand factor outside peak weeks
    "seasonal_profiles": {
        "flat": {
            "summer": {"peak_weeks": [],          "multiplier": 1.0,  "off_multiplier": 1.0},
            "winter": {"peak_weeks": [],          "multiplier": 1.0,  "off_multiplier": 1.0},
        },
        "summer": {
            "summer": {"peak_weeks": list(range(22, 33)),  "multiplier": 1.5,  "off_multiplier": 0.8},
            "winter": {"peak_weeks": list(range(22, 33)),  "multiplier": 0.7,  "off_multiplier": 1.0},
        },
        "mild": {
            "summer": {"peak_weeks": list(range(20, 35)),  "multiplier": 1.3,  "off_multiplier": 0.9},
            "winter": {"peak_weeks": list(range(44, 53)) + list(range(1, 9)), "multiplier": 1.1, "off_multiplier": 0.95},
        },
        "winter": {
            "summer": {"peak_weeks": list(range(44, 53)) + list(range(1, 9)), "multiplier": 0.5, "off_multiplier": 1.0},
            "winter": {"peak_weeks": list(range(44, 53)) + list(range(1, 9)), "multiplier": 1.6, "off_multiplier": 0.6},
        },
        "strongwinter": {
            "summer": {"peak_weeks": list(range(44, 53)) + list(range(1, 9)), "multiplier": 0.05, "off_multiplier": 0.3},
            "winter": {"peak_weeks": list(range(44, 53)) + list(range(1, 9)), "multiplier": 3.0,  "off_multiplier": 0.2},
        },
        "holiday": {
            "summer": {"peak_weeks": list(range(48, 53)),  "multiplier": 1.5,  "off_multiplier": 0.7},
            "winter": {"peak_weeks": list(range(48, 53)),  "multiplier": 2.0,  "off_multiplier": 0.6},
        },
        "formalholiday": {
            "summer": {"peak_weeks": list(range(12, 17)) + list(range(48, 53)), "multiplier": 1.5, "off_multiplier": 0.4},
            "winter": {"peak_weeks": list(range(48, 53)),  "multiplier": 2.5,  "off_multiplier": 0.3},
        },
    },

    # ── Weekend uplift (Friday=4, Saturday=5 in Python weekday, 0=Monday) ─────
    "weekend_uplift_dow": [4, 5],   # Friday, Saturday
    "weekend_uplift_factor": 1.3,
    "weekend_velocity_classes": ["fast", "medium"],

    # ── Lumpy spike parameters ─────────────────────────────────────────────────
    "lumpy_spike_probability": 0.06,   # 6% chance of a spike day
    "lumpy_spike_multiplier": 8,

    # ── Rare demand outlier ────────────────────────────────────────────────────
    "outlier_probability": 0.002,      # 0.2% chance per store-item-day
    "outlier_multiplier": 5,

    # ── Supplier lead times (days) ─────────────────────────────────────────────
    "lead_time_range": {"min": 7, "max": 21},

    # ── Receipt randomness ─────────────────────────────────────────────────────
    "p_late": 0.15,
    "late_days_min": 1,
    "late_days_max": 7,
    "p_partial": 0.10,
    "partial_frac_min": 0.60,
    "partial_frac_max": 0.90,
    "remainder_gap_min": 3,
    "remainder_gap_max": 10,

    # ── Replenishment ──────────────────────────────────────────────────────────
    "store_coverage_days": {
        "fast":   7,
        "medium": 10,
        "slow":   14,
        "lumpy":  21,
    },
    "dc_coverage_days": 28,
    "demand_smoothing_window": 28,     # days for moving average
    "dc_review_dow": 0,                # 0 = Monday

    # ── Initial inventory seeding ──────────────────────────────────────────────
    "dc_init_coverage_days": 30,       # DC starts with 30 days of avg demand
    "store_init_coverage_days": 5,     # Stores start with 5 days of avg demand

    # ── Site regions ───────────────────────────────────────────────────────────
    "regions": ["Northeast", "South", "West"],
}
