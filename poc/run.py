"""
Entry point - run with:   python run.py

Reads CONFIG from config.py, builds all feeds, writes them to:
    output/<run_id>_<scenario>/feeds_txt/
    output/<run_id>_<scenario>/feeds_excel/
"""

import os
import sys
import json
import time
from datetime import date, timedelta

# Add poc/ to path so imports work from the project root too
sys.path.insert(0, os.path.dirname(__file__))

from config import CONFIG
import calendar_builder
import master_data as md_builder
import demand as demand_builder
import simulation
import chips_only_simulation


CATEGORY_CALENDAR = "calendar and currency feeds"
CATEGORY_MASTER = "master data feeds"
CATEGORY_SIMULATION = "simulation feeds"


def resolve_dates(cfg):
    """Derive start_date and end_date from scenario + history_weeks."""
    scenario = cfg["scenario"]
    weeks    = cfg["history_weeks"]

    if scenario == "summer":
        start = date(2024, 4, 1)   # April 1 — summer season centred at week 22-32
    elif scenario == "winter":
        start = date(2024, 10, 1)  # Oct 1 — winter season centred at week 44-52
    else:
        raise ValueError(f"Unknown scenario: {scenario!r}. Use 'summer' or 'winter'.")

    end = start + timedelta(weeks=weeks) - timedelta(days=1)
    return start, end


def build_date_list(start_date, end_date):
    dates = []
    d = start_date
    while d <= end_date:
        dates.append(d)
        d += timedelta(days=1)
    return dates


def list_files_recursive(root_dir):
    files = []
    if not os.path.isdir(root_dir):
        return files

    for dirpath, _, filenames in os.walk(root_dir):
        filenames.sort()
        for filename in filenames:
            full_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(full_path, root_dir).replace("\\", "/")
            files.append(rel_path)

    files.sort()
    return files


def ensure_excel_dependencies():
    try:
        import pandas as pd
        import openpyxl  # noqa: F401
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "Excel export requires pandas and openpyxl. "
            "Install them with: pip install pandas openpyxl"
        ) from exc
    return pd


def convert_txt_to_excel(feeds_txt_root, feeds_excel_root):
    pd = ensure_excel_dependencies()

    txt_files = [
        rel_path for rel_path in list_files_recursive(feeds_txt_root)
        if rel_path.lower().endswith(".txt")
    ]
    excel_files = []

    for rel_txt_path in txt_files:
        txt_path = os.path.join(feeds_txt_root, rel_txt_path)
        rel_xlsx_path = rel_txt_path[:-4] + ".xlsx"
        xlsx_path = os.path.join(feeds_excel_root, rel_xlsx_path)
        os.makedirs(os.path.dirname(xlsx_path), exist_ok=True)

        df = pd.read_csv(txt_path, sep="|", dtype=str, keep_default_na=False)
        df.to_excel(xlsx_path, index=False, engine="openpyxl")
        excel_files.append(rel_xlsx_path.replace("\\", "/"))

    excel_files.sort()
    return txt_files, excel_files


def main():
    cfg = CONFIG
    t0  = time.time()

    scenario   = cfg["scenario"]
    run_id     = cfg["run_id"]
    start, end = resolve_dates(cfg)

    output_folder = os.path.join(
        os.path.dirname(__file__), "..", "output", f"{run_id}_{scenario}"
    )
    feeds_txt_root = os.path.join(output_folder, "feeds_txt")
    feeds_excel_root = os.path.join(output_folder, "feeds_excel")

    calendar_txt_dir = os.path.join(feeds_txt_root, CATEGORY_CALENDAR)
    master_txt_dir = os.path.join(feeds_txt_root, CATEGORY_MASTER)
    simulation_txt_dir = os.path.join(feeds_txt_root, CATEGORY_SIMULATION)

    os.makedirs(calendar_txt_dir, exist_ok=True)
    os.makedirs(master_txt_dir, exist_ok=True)
    os.makedirs(simulation_txt_dir, exist_ok=True)

    print(f"\n{'='*60}")
    print(f" Clothing Pre-MVP Synthetic Data Generator")
    print(f" Run ID     : {run_id}")
    print(f" Scenario   : {scenario.upper()}")
    print(f" Dates      : {start} -> {end}  ({cfg['history_weeks']} weeks)")
    print(
        f" Scale      : {cfg['store_count']} stores | 1 DC | "
        f"{cfg['item_count']} items | {cfg['supplier_count']} suppliers"
    )
    print(f" TXT Root   : {os.path.abspath(feeds_txt_root)}")
    print(f" Excel Root : {os.path.abspath(feeds_excel_root)}")
    print(f"{'='*60}\n")

    dates = build_date_list(start, end)

    # ── Phase 1: Calendar + Currency ──────────────────────────────────────────
    print("[1/5] Building calendar and currency feeds ...")
    calendar_builder.build_calendar(start, end, calendar_txt_dir)
    calendar_builder.build_currency(cfg["base_currency"], start, end, calendar_txt_dir)

    # ── Phase 2: Master data + group feeds ────────────────────────────────────
    print("\n[2/5] Building master data feeds ...")
    md = md_builder.build_master_data(cfg, master_txt_dir)

    # ── Phase 3: Demand matrix ────────────────────────────────────────────────
    print("\n[3/5] Generating demand matrix ...")
    demand_array, story_state = demand_builder.build_demand(cfg, md, dates)

    # ── Phase 4: Simulation ───────────────────────────────────────────────────
    print("\n[4/5] Running B1 simulation ...")
    if cfg.get("simulation_engine", "default") == "chips_only":
        chips_only_simulation.run_chips_only_simulation(
            cfg, md, dates, demand_array, simulation_txt_dir, story_state
        )
    else:
        simulation.run_simulation(cfg, md, dates, demand_array, simulation_txt_dir, story_state)

    # ── Phase 5: Excel copies ─────────────────────────────────────────────────
    print("\n[5/5] Creating Excel feed copies ...")
    txt_files, excel_files = convert_txt_to_excel(feeds_txt_root, feeds_excel_root)

    # ── Manifest ──────────────────────────────────────────────────────────────
    elapsed = round(time.time() - t0, 1)
    manifest = {
        "run_id":    run_id,
        "scenario":  scenario,
        "start_date": str(start),
        "end_date":   str(end),
        "seed":       cfg["seed"],
        "stores":     cfg["store_count"],
        "dcs":        cfg["dc_count"],
        "items":      cfg["item_count"],
        "suppliers":  cfg["supplier_count"],
        "elapsed_s":  elapsed,
        "feeds_txt_root": os.path.abspath(feeds_txt_root),
        "feeds_excel_root": os.path.abspath(feeds_excel_root),
        "txt_files": txt_files,
        "excel_files": excel_files,
        # Backward-compatible keys from previous manifest format.
        "feeds_dir": os.path.abspath(feeds_txt_root),
        "files": txt_files,
    }
    manifest_path = os.path.join(output_folder, "run_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n{'='*60}")
    print(f" Done in {elapsed}s")
    print(f" TXT feeds   : {len(txt_files)} files")
    print(f" {os.path.abspath(feeds_txt_root)}")
    print(f" Excel feeds : {len(excel_files)} files")
    print(f" {os.path.abspath(feeds_excel_root)}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
