"""Scenario overlay engine for story-driven daily-loop simulations.

This module applies deterministic overrides on top of baseline synthetic demand
and provides day-level supply caps to shape the simulation into explainable
narratives (promo spikes, shortages, recoveries, size-mix issues).
"""

from typing import Dict, Tuple
import numpy as np


def _build_story_index(md) -> Dict[str, int]:
    """Map story keys (chips, jeans_30, etc.) to item indices."""
    story_index = {}
    for idx, item_code in enumerate(md.item_codes):
        key = md.item_story_key.get(item_code)
        if key:
            story_index[key] = idx
    return story_index


def _set_absolute_daily_demand(demand_int, item_idx, day_values, stores=None):
    """Overwrite demand with absolute daily values for specific days."""
    n_stores = demand_int.shape[0]
    target_stores = list(range(n_stores)) if stores is None else stores
    n_days = demand_int.shape[2]
    for day_idx, value in enumerate(day_values):
        if day_idx >= n_days:
            break
        for s in target_stores:
            demand_int[s, item_idx, day_idx] = int(max(0, value))


def apply_demand_story_overrides(cfg, md, demand_int, dates):
    """Apply story pack demand overrides in-place and return story state."""
    story_pack = cfg.get("scenario_pack", "none")
    story_idx = _build_story_index(md)

    story_state = {
        "pack": story_pack,
        "story_item_index": story_idx,
        "rule_labels": {},            # (day_idx, store_idx, item_idx) -> label
        "dc_to_store_caps": {},       # day_idx -> {item_idx: cap}
        "supplier_to_dc_caps": {},    # day_idx -> {item_idx: cap}
    }

    if story_pack == "none":
        return story_state

    if story_pack == "potato_chips_story":
        chips_idx = story_idx.get("chips")
        if chips_idx is not None:
            # Days 1..7 from the narrative (0-based indexing).
            chips_day_demand = [30, 30, 60, 60, 60, 60, 45]
            _set_absolute_daily_demand(demand_int, chips_idx, chips_day_demand)

            for d in range(min(7, demand_int.shape[2])):
                for s in range(demand_int.shape[0]):
                    story_state["rule_labels"][(d, s, chips_idx)] = "POTATO_CHIPS_STORY"

            # DC->store shipping caps on shortage and recovery days.
            # Day 5 cap=20, Day 6 cap=20, Day 7 cap=50 (narrative days).
            story_state["dc_to_store_caps"][4] = {chips_idx: 20}
            story_state["dc_to_store_caps"][5] = {chips_idx: 20}
            story_state["dc_to_store_caps"][6] = {chips_idx: 50}

    elif story_pack == "blue_jeans_story":
        s0 = [0]  # Story is focused on one showcase store.
        j30 = story_idx.get("jeans_30")
        j32 = story_idx.get("jeans_32")
        j34 = story_idx.get("jeans_34")

        # 6-day profile from the narrative.
        if j30 is not None:
            _set_absolute_daily_demand(demand_int, j30, [4, 4, 6, 6, 5, 4], stores=s0)
        if j32 is not None:
            _set_absolute_daily_demand(demand_int, j32, [2, 2, 3, 3, 2, 2], stores=s0)
        if j34 is not None:
            _set_absolute_daily_demand(demand_int, j34, [1, 1, 1, 1, 1, 1], stores=s0)

        for d in range(min(6, demand_int.shape[2])):
            for idx in [j30, j32, j34]:
                if idx is not None:
                    story_state["rule_labels"][(d, 0, idx)] = "BLUE_JEANS_STORY"

        # Key-size constrained supply (size 30).
        if j30 is not None:
            # Day 4 and Day 5 cap the key size to mimic wrong-mix behavior.
            story_state["dc_to_store_caps"][3] = {j30: 2}
            story_state["dc_to_store_caps"][4] = {j30: 2}

    return story_state


def get_day_dc_to_store_caps(story_state, day_idx):
    """Return item caps for DC->store shipment on this day."""
    return story_state.get("dc_to_store_caps", {}).get(day_idx, {})


def get_day_supplier_to_dc_caps(story_state, day_idx):
    """Return item caps for supplier->DC receipts on this day."""
    return story_state.get("supplier_to_dc_caps", {}).get(day_idx, {})


def get_rule_label(story_state, day_idx, store_idx, item_idx):
    """Return scenario rule label for this day/store/item if any."""
    return story_state.get("rule_labels", {}).get((day_idx, store_idx, item_idx), "")
