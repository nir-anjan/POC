"""
Master data builder — generates Sites, Items, Suppliers, and all group feeds.

Returns a MasterData dataclass holding all lookup tables needed by the
simulation engine and writers.
"""

import random
from dataclasses import dataclass, field
from typing import Dict, List
import writers


# ── Clothing size / style / colour pools ──────────────────────────────────────
SIZES = {
    "BASICS":      ["XS","S","M","L","XL","XXL"],
    "TOPS":        ["XS","S","M","L","XL","XXL"],
    "BOTTOMS":     ["28","30","32","34","36","38"],
    "FOOTWEAR":    ["6","7","8","9","10","11","12"],
    "OUTERWEAR":   ["XS","S","M","L","XL"],
    "ACCESSORIES": ["One Size"],
    "FORMALWEAR":  ["XS","S","M","L","XL"],
}
SIZE_TYPES = {
    "BASICS":      "Alpha",
    "TOPS":        "Alpha",
    "BOTTOMS":     "Waist",
    "FOOTWEAR":    "UK Shoe",
    "OUTERWEAR":   "Alpha",
    "ACCESSORIES": "Universal",
    "FORMALWEAR":  "Alpha",
}
COLOURS = ["Black","White","Navy","Grey","Red","Green","Blue","Beige","Brown","Khaki"]
STYLES_PREFIX = {
    "BASICS":      "BSC",
    "TOPS":        "TOP",
    "BOTTOMS":     "BTM",
    "FOOTWEAR":    "FTW",
    "OUTERWEAR":   "OTW",
    "ACCESSORIES": "ACC",
    "FORMALWEAR":  "FML",
}


@dataclass
class MasterData:
    # Site lists
    dc_codes: List[str] = field(default_factory=list)
    store_codes: List[str] = field(default_factory=list)

    # Item lists
    item_codes: List[str] = field(default_factory=list)

    # Supplier list
    supplier_codes: List[str] = field(default_factory=list)

    # Item lookups
    item_supplier: Dict[str, str] = field(default_factory=dict)   # item → supplier
    item_velocity: Dict[str, str] = field(default_factory=dict)   # item → velocity class
    item_category: Dict[str, str] = field(default_factory=dict)   # item → category code
    item_seasonal: Dict[str, str] = field(default_factory=dict)   # item → seasonal profile
    item_story_key: Dict[str, str] = field(default_factory=dict)  # item → story key
    item_sell_price: Dict[str, float] = field(default_factory=dict)
    item_cost_price: Dict[str, float] = field(default_factory=dict)

    # Supplier lookups
    supplier_lead_time: Dict[str, int] = field(default_factory=dict)  # supplier → lead days

    # Site lookups
    site_region: Dict[str, str] = field(default_factory=dict)
    site_type: Dict[str, str] = field(default_factory=dict)

    # Currency
    base_currency: str = "USD"


def build_master_data(cfg, feeds_dir) -> MasterData:
    rng = random.Random(cfg["seed"])
    md = MasterData(base_currency=cfg["base_currency"])

    # ── Sites ──────────────────────────────────────────────────────────────────
    site_rows = []

    # DCs
    for i in range(1, cfg["dc_count"] + 1):
        code = f"DC_{i:02d}"
        md.dc_codes.append(code)
        md.site_type[code] = "DC"
        md.site_region[code] = "HQ"
        site_rows.append({
            "SiteCode":           code,
            "CurrencyCode":       cfg["base_currency"],
            "SiteName":           f"Distribution Centre {i:02d}",
            "CountryCode":        "US",
            "SiteStatus":         "O",
            "HostSystemLeadTime": 1,
            "SiteRegion":         "HQ",
            "SiteType":           "DC",
        })

    # Stores
    regions = cfg["regions"]
    for i in range(1, cfg["store_count"] + 1):
        code = f"STORE_{i:03d}"
        region = regions[(i - 1) % len(regions)]
        md.store_codes.append(code)
        md.site_type[code] = "Store"
        md.site_region[code] = region
        site_rows.append({
            "SiteCode":           code,
            "CurrencyCode":       cfg["base_currency"],
            "SiteName":           f"Clothing Store {region[:3].upper()}{i:03d}",
            "CountryCode":        "US",
            "SiteStatus":         "O",
            "HostSystemLeadTime": "",
            "SiteRegion":         region,
            "SiteType":           "Store",
        })

    writers.write_feed(f"{feeds_dir}/Site.txt", site_rows, writers.SITE_COLUMNS)
    print(f"  Site.txt             — {len(site_rows)} rows")

    # ── Suppliers ──────────────────────────────────────────────────────────────
    supplier_rows = []
    lt_min = cfg["lead_time_range"]["min"]
    lt_max = cfg["lead_time_range"]["max"]
    supplier_names = [
        "ThreadForward Ltd", "FabricHouse Co", "NexStyle Garments",
        "PremierWeave Inc", "UrbanThread Supply", "AlphaCloth Group",
        "EliteTextile Corp", "SwiftStitch Ltd", "GlobalFibre Works", "ModaCraft Inc",
    ]
    for i in range(1, cfg["supplier_count"] + 1):
        code = f"SUP_{i:03d}"
        lead = rng.randint(lt_min, lt_max)
        md.supplier_codes.append(code)
        md.supplier_lead_time[code] = lead
        supplier_rows.append({
            "SupplierCode":       code,
            "SupplierName":       supplier_names[i - 1],
            "HostSystemLeadTime": lead,
            "SupplierActiveFlag": 1,
        })

    writers.write_feed(f"{feeds_dir}/Supplier.txt", supplier_rows, writers.SUPPLIER_COLUMNS)
    print(f"  Supplier.txt         — {len(supplier_rows)} rows")

    # ── Items ──────────────────────────────────────────────────────────────────
    item_rows = []
    item_seq = 1
    dept_keys = list(cfg["departments"].keys())

    story_items = cfg.get("story_items", [])

    if story_items:
        for j, s_item in enumerate(story_items):
            item_code = s_item["code"]
            cat_code = s_item["category"]
            velocity = s_item["velocity"]
            seasonal = s_item["seasonal"]
            p_range = cfg["price_ranges"][cat_code]

            size = s_item.get("size", SIZES[cat_code][j % len(SIZES[cat_code])])
            size_type = s_item.get("size_type", SIZE_TYPES[cat_code])
            style = s_item.get("style", f"{STYLES_PREFIX[cat_code]}_{j+1:03d}")
            colour = s_item.get("color", COLOURS[j % len(COLOURS)])
            supplier = md.supplier_codes[j % len(md.supplier_codes)]
            sell_price = round(rng.uniform(p_range["min"], p_range["max"]), 2)
            cost_price = round(sell_price * p_range["cost_pct"], 2)

            md.item_codes.append(item_code)
            md.item_supplier[item_code] = supplier
            md.item_velocity[item_code] = velocity
            md.item_category[item_code] = cat_code
            md.item_seasonal[item_code] = seasonal
            md.item_story_key[item_code] = s_item.get("story_key", "")
            md.item_sell_price[item_code] = sell_price
            md.item_cost_price[item_code] = cost_price

            item_rows.append({
                "ItemCode": item_code,
                "ProductDescription": s_item.get("description", f"{colour} {cat_code.title()} {size} ({style})"),
                "ExternalItemMasterID": f"EXT-{item_code}",
                "SizeName": size,
                "SizeTypeName": size_type,
                "StyleCode": style,
                "ColorCode": colour,
                "VariantCode": f"{style}-{colour[:3].upper()}-{size}",
                "ActiveFlag": 1,
            })
            item_seq += 1
    else:
        for cat in cfg["categories"]:
            cat_code = cat["code"]
            velocity = cat["velocity"]
            seasonal = cat["seasonal"]
            p_range  = cfg["price_ranges"][cat_code]
            sizes    = SIZES[cat_code]
            size_type = SIZE_TYPES[cat_code]
            style_pfx = STYLES_PREFIX[cat_code]

            for j in range(cat["count"]):
                item_code = f"ITM_{cat_code[:3]}_{item_seq:04d}"
                size      = sizes[j % len(sizes)]
                colour    = COLOURS[j % len(COLOURS)]
                dept      = dept_keys[j % len(dept_keys)]
                style     = f"{style_pfx}_{j+1:03d}"
                sell_price = round(rng.uniform(p_range["min"], p_range["max"]), 2)
                cost_price = round(sell_price * p_range["cost_pct"], 2)
                supplier   = md.supplier_codes[item_seq % len(md.supplier_codes)]

                md.item_codes.append(item_code)
                md.item_supplier[item_code]    = supplier
                md.item_velocity[item_code]    = velocity
                md.item_category[item_code]    = cat_code
                md.item_seasonal[item_code]    = seasonal
                md.item_story_key[item_code]   = ""
                md.item_sell_price[item_code]  = sell_price
                md.item_cost_price[item_code]  = cost_price

                item_rows.append({
                    "ItemCode":            item_code,
                    "ProductDescription":  f"{colour} {cat_code.title()} {size} ({style})",
                    "ExternalItemMasterID": f"EXT-{item_code}",
                    "SizeName":            size,
                    "SizeTypeName":        size_type,
                    "StyleCode":           style,
                    "ColorCode":           colour,
                    "VariantCode":         f"{style}-{colour[:3].upper()}-{size}",
                    "ActiveFlag":          1,
                })
                item_seq += 1

    writers.write_feed(f"{feeds_dir}/ItemMaster.txt", item_rows, writers.ITEM_COLUMNS)
    print(f"  ItemMaster.txt       — {len(item_rows)} rows")

    # ── Group feeds ────────────────────────────────────────────────────────────

    # ItemMasterGroup1 — Department
    g1_rows = [
        {"ItemMasterGroup1Code": k, "ItemMasterGroup1Description": v}
        for k, v in cfg["departments"].items()
    ]
    writers.write_feed(f"{feeds_dir}/ItemMasterGroup1.txt", g1_rows, writers.ITEM_MASTER_GROUP1_COLUMNS)
    print(f"  ItemMasterGroup1.txt — {len(g1_rows)} rows")

    # ItemMasterGroup2 — Category
    g2_rows = [
        {"ItemMasterGroup2Code": cat["code"], "ItemMasterGroup2Description": cat["description"]}
        for cat in cfg["categories"]
    ]
    writers.write_feed(f"{feeds_dir}/ItemMasterGroup2.txt", g2_rows, writers.ITEM_MASTER_GROUP2_COLUMNS)
    print(f"  ItemMasterGroup2.txt — {len(g2_rows)} rows")

    # ItemMasterGroup3 — Velocity
    g3_rows = [
        {"ItemMasterGroup3Code": v, "ItemMasterGroup3Description": v.title() + " Moving"}
        for v in ["fast", "medium", "slow", "lumpy"]
    ]
    writers.write_feed(f"{feeds_dir}/ItemMasterGroup3.txt", g3_rows, writers.ITEM_MASTER_GROUP3_COLUMNS)
    print(f"  ItemMasterGroup3.txt — {len(g3_rows)} rows")

    # ItemMasterGroup.txt — link table
    dept_keys_list = list(cfg["departments"].keys())
    gd_rows = []
    for idx, item_code in enumerate(md.item_codes):
        dept = dept_keys_list[idx % len(dept_keys_list)]
        gd_rows.append({
            "ItemCode":             item_code,
            "ItemMasterGroup1Code": dept,
            "ItemMasterGroup2Code": md.item_category[item_code],
            "ItemMasterGroup3Code": md.item_velocity[item_code],
        })
    writers.write_feed(f"{feeds_dir}/ItemMasterGroup.txt", gd_rows, writers.ITEM_MASTER_GROUP_DETAIL_COLUMNS)
    print(f"  ItemMasterGroup.txt  — {len(gd_rows)} rows")

    # SiteGroup1 — Region
    unique_regions = list(dict.fromkeys(cfg["regions"]))
    sg1_rows = [
        {"SiteGroup1Code": r, "SiteGroup1Description": r + " Region"}
        for r in unique_regions
    ]
    writers.write_feed(f"{feeds_dir}/SiteGroup1.txt", sg1_rows, writers.SITE_GROUP1_COLUMNS)
    print(f"  SiteGroup1.txt       — {len(sg1_rows)} rows")

    # SiteGroup2 — Site type
    sg2_rows = [
        {"SiteGroup2Code": "Store", "SiteGroup2Description": "Retail Store"},
        {"SiteGroup2Code": "DC",    "SiteGroup2Description": "Distribution Centre"},
    ]
    writers.write_feed(f"{feeds_dir}/SiteGroup2.txt", sg2_rows, writers.SITE_GROUP2_COLUMNS)
    print(f"  SiteGroup2.txt       — {len(sg2_rows)} rows")

    return md
