"""
Demand generator — precomputes requested_qty[store_idx, item_idx, day_idx].

Returns a numpy int32 array of shape (n_stores, n_items, n_days).
All randomness is seeded deterministically from cfg["seed"].
"""

import numpy as np
from datetime import timedelta


def _iso_week(d):
    return d.isocalendar()[1]   # ISO week number 1-52


def build_demand(cfg, md, dates) -> np.ndarray:
    """
    cfg    : CONFIG dict
    md     : MasterData
    dates  : list of date objects (the simulation horizon)

    Returns demand[store_idx, item_idx, day_idx] as int32 numpy array.
    """
    rng = np.random.default_rng(cfg["seed"] + 1)
    scenario = cfg["scenario"]

    n_stores = len(md.store_codes)
    n_items  = len(md.item_codes)
    n_days   = len(dates)

    demand = np.zeros((n_stores, n_items, n_days), dtype=np.float32)

    # Precompute day-level attributes
    weekdays    = np.array([d.weekday() for d in dates], dtype=np.int8)   # 0=Mon
    iso_weeks   = np.array([_iso_week(d) for d in dates], dtype=np.int8)

    seasonal_profiles = cfg["seasonal_profiles"]
    base_demand_cfg   = cfg["base_demand"]
    weekend_dows      = set(cfg["weekend_uplift_dow"])
    weekend_factor    = cfg["weekend_uplift_factor"]
    weekend_classes   = set(cfg["weekend_velocity_classes"])

    for i_item, item_code in enumerate(md.item_codes):
        velocity = md.item_velocity[item_code]
        seasonal_key = md.item_seasonal[item_code]
        bd = base_demand_cfg[velocity]

        profile = seasonal_profiles[seasonal_key][scenario]
        peak_weeks_set = set(profile["peak_weeks"])
        peak_mult   = profile["multiplier"]
        off_mult    = profile["off_multiplier"]

        # Base mean demand per store-day (float)
        base_mean = rng.uniform(bd["min"], bd["max"])

        # Seasonal multiplier per day (broadcast over stores later)
        season_mult = np.where(
            np.isin(iso_weeks, list(peak_weeks_set)),
            peak_mult,
            off_mult,
        ).astype(np.float32)    # shape (n_days,)

        # Weekend uplift per day
        weekend_mult = np.ones(n_days, dtype=np.float32)
        if velocity in weekend_classes:
            for dow in weekend_dows:
                weekend_mult[weekdays == dow] *= weekend_factor

        combined_mult = season_mult * weekend_mult  # (n_days,)

        # Generate Poisson demand for each store independently
        lambda_mat = base_mean * combined_mult  # (n_days,) broadcast over stores
        # shape: (n_stores, n_days)
        item_demand = rng.poisson(
            lambda_mat[np.newaxis, :].repeat(n_stores, axis=0)
        ).astype(np.float32)

        # Lumpy items: zero out most days, add spikes
        if velocity == "lumpy":
            spike_prob = cfg["lumpy_spike_probability"]
            spike_mult = cfg["lumpy_spike_multiplier"]
            # Only keep demand on spike days; zero everything else
            spike_mask = rng.random((n_stores, n_days)) < spike_prob
            item_demand = item_demand * spike_mask * spike_mult

        # Rare outliers (applies to all velocities)
        outlier_prob = cfg["outlier_probability"]
        outlier_mult = cfg["outlier_multiplier"]
        outlier_mask = rng.random((n_stores, n_days)) < outlier_prob
        item_demand[outlier_mask] *= outlier_mult

        demand[:, i_item, :] = item_demand

    # Store-level scaling: each store gets a mild scale factor (0.7-1.3)
    # to give variety across stores without changing overall demand shape
    store_scale = rng.uniform(0.7, 1.3, size=(n_stores, 1, 1)).astype(np.float32)
    demand = demand * store_scale

    # Convert to integers (round, clamp >= 0)
    demand_int = np.round(demand).astype(np.int32)
    demand_int = np.maximum(demand_int, 0)

    total = demand_int.sum()
    print(f"  Demand matrix        — shape {demand_int.shape}, total units={total:,}")
    return demand_int
