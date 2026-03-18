"""Chips-only simulation engine with table-style daily output.

This module is intentionally scoped to one narrative item (potato chips)
and provides a compact table format in terminal plus a persisted table feed.
"""

import numpy as np
import writers
import scenario_engine


def _find_chips_item_index(md):
    for i, item_code in enumerate(md.item_codes):
        if md.item_story_key.get(item_code) == "chips":
            return i
    if md.item_codes:
        return 0
    raise ValueError("No items available for chips-only simulation")


def _prompt_non_negative_int(label, default_value):
    """Prompt user for a non-negative integer with a default fallback."""
    while True:
        raw = input(f"  {label} [{default_value}]: ").strip()
        if raw == "":
            return int(default_value)
        try:
            value = int(raw)
            if value < 0:
                print("  Please enter a non-negative integer.")
                continue
            return value
        except ValueError:
            print("  Invalid number. Enter a whole number (0 or higher).")


def _resolve_initial_stock(cfg, md, default_dc_stock, default_store_stock):
    """Resolve initial stocks either from terminal prompts or config overrides."""
    use_prompt = cfg.get("prompt_initial_stock", True)

    if not use_prompt:
        dc = int(cfg.get("initial_stock_dc", default_dc_stock))
        stores_map = cfg.get("initial_stock_stores", {})
        stores = np.array(
            [int(stores_map.get(store_code, default_store_stock)) for store_code in md.store_codes],
            dtype=np.int64,
        )
        return dc, stores

    print("\n  Set Initial Stock Values (press Enter to keep default):")
    dc = _prompt_non_negative_int("DC_001 opening stock", default_dc_stock)
    stores = np.zeros(len(md.store_codes), dtype=np.int64)
    for si, store_code in enumerate(md.store_codes):
        stores[si] = _prompt_non_negative_int(f"{store_code} opening stock", default_store_stock)
    return int(dc), stores


def _print_day_table(day, rows, shortage_started):
    print("")
    print(f"  === Chips Table | {day} ===")
    print("  +----------+--------+------+-------+-------+-------+--------+------+")
    print("  | Store    | Demand | Need | Ship  | Deliv | Unmet | Before | Left |")
    print("  +----------+--------+------+-------+-------+-------+--------+------+")

    day_has_tightness = False
    day_has_unmet = False
    for r in rows:
        if r["FillNeeded"] > r["Shipped"]:
            day_has_tightness = True
        if r["UnmetDemand"] > 0:
            day_has_unmet = True
        print(
            f"  | {r['SiteCode']:<8} | {r['Demand']:>6} | {r['FillNeeded']:>4} |"
            f" {r['Shipped']:>5} | {r['Delivered']:>5} | {r['UnmetDemand']:>5} |"
            f" {r['StockBefore']:>6} | {r['StockLeft']:>4} |"
        )

    print("  +----------+--------+------+-------+-------+-------+--------+------+")
    if day_has_tightness and not shortage_started:
        print("  >>> SHORTAGE EFFECT START: replenishment constrained <<<")
        shortage_started = True
    elif day_has_tightness:
        print("  >>> SHORTAGE EFFECT CONTINUES: replenishment constrained <<<")
    if day_has_unmet:
        print("  >>> STOCKOUT IMPACT: unmet demand observed <<<")
    return shortage_started


def run_chips_only_simulation(cfg, md, dates, demand_array, feeds_dir, story_state=None):
    n_stores = len(md.store_codes)
    chips_idx = _find_chips_item_index(md)
    chips_code = md.item_codes[chips_idx]

    avg_daily_chips = float(demand_array[:, chips_idx, :].mean())
    default_dc_stock = int(max(0, round(avg_daily_chips * cfg["dc_init_coverage_days"] * n_stores)))
    default_store_stock = int(max(0, round(avg_daily_chips * cfg["store_init_coverage_days"])))
    dc_stock, store_stock = _resolve_initial_stock(cfg, md, default_dc_stock, default_store_stock)

    rows_table = []
    shortage_started = False

    if story_state is None:
        story_state = {
            "pack": "none",
            "dc_to_store_caps": {},
            "supplier_to_dc_caps": {},
            "rule_labels": {},
        }

    smooth_win = cfg["demand_smoothing_window"]
    chips_velocity = md.item_velocity[chips_code]
    chips_cov_days = cfg["store_coverage_days"][chips_velocity]

    print(f"\n  Running chips-only simulation for item: {chips_code}")
    print("  Initial Stock Snapshot:")
    print("  +----------------------+------------+")
    print("  | Location             | StockOnHand|")
    print("  +----------------------+------------+")
    print(f"  | {'DC_001':<20} | {dc_stock:>10} |")
    for si, store_code in enumerate(md.store_codes):
        print(f"  | {store_code:<20} | {int(store_stock[si]):>10} |")
    print("  +----------------------+------------+")

    for day_idx, day in enumerate(dates):
        d_str = writers.fmt_date(day)

        # Demand and fill need.
        demand_today = demand_array[:, chips_idx, day_idx].astype(np.int64)
        win_start = max(0, day_idx - smooth_win + 1)
        avg_store = demand_array[:, chips_idx, win_start:day_idx + 1].mean(axis=1)
        fill_needed = np.maximum(np.round(avg_store * chips_cov_days).astype(np.int64) - store_stock, 0)

        # Shipment allocation with optional story cap.
        total_need = int(fill_needed.sum())
        ship = np.zeros(n_stores, dtype=np.int64)
        available = int(max(0, dc_stock))
        if total_need > 0 and available > 0:
            if available >= total_need:
                ship = fill_needed.copy()
            else:
                prop = available * fill_needed / total_need
                ship = np.floor(prop).astype(np.int64)
                rem = available - int(ship.sum())
                if rem > 0:
                    frac = prop - ship
                    top = np.argsort(frac)[::-1][:rem]
                    ship[top] += 1

        cap = scenario_engine.get_day_dc_to_store_caps(story_state, day_idx).get(chips_idx)
        if cap is not None:
            cap = int(max(0, cap))
            cur = int(ship.sum())
            if cur > cap:
                prop = cap * ship / max(1, cur)
                ship = np.floor(prop).astype(np.int64)
                rem = cap - int(ship.sum())
                if rem > 0:
                    frac = prop - ship
                    top = np.argsort(frac)[::-1][:rem]
                    ship[top] += 1

        # Apply shipments.
        dc_stock -= int(ship.sum())
        dc_stock = max(0, dc_stock)
        stock_before = store_stock + ship

        # Deliver from store stock.
        delivered = np.minimum(demand_today, stock_before)
        unmet = np.maximum(demand_today - delivered, 0)
        store_stock = stock_before - delivered

        day_rows = []
        for si, store_code in enumerate(md.store_codes):
            row = {
                "Date": d_str,
                "SiteCode": store_code,
                "ItemCode": chips_code,
                "Demand": int(demand_today[si]),
                "FillNeeded": int(fill_needed[si]),
                "Shipped": int(ship[si]),
                "Delivered": int(delivered[si]),
                "UnmetDemand": int(unmet[si]),
                "StockBefore": int(stock_before[si]),
                "StockLeft": int(store_stock[si]),
            }
            rows_table.append(row)
            day_rows.append(row)

        shortage_started = _print_day_table(day, day_rows, shortage_started)
        print(f"  DC_Stock={dc_stock}")

    writers.write_feed(
        f"{feeds_dir}/ChipsDailyTable.txt",
        rows_table,
        [
            "Date", "SiteCode", "ItemCode", "Demand", "FillNeeded", "Shipped",
            "Delivered", "UnmetDemand", "StockBefore", "StockLeft",
        ],
    )
    print(f"  {'ChipsDailyTable.txt':<30} — {len(rows_table):>8,} rows")
