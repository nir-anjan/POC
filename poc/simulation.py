"""
B1 Simulation Engine — daily loop.

Step order (per spec):
  1. Post supplier receipts into DC
  2. Create customer orders (store demand)
  3. Compute store replenishment needs
  4. Allocate DC→store shipments (IBTs)
  5. Fulfill deliveries at stores
  6. Write sales history
  7. Create supplier POs (DC weekly review, Mondays only)
  8. Write end-of-day inventory snapshot

Writes all transactional feeds + Inventory.txt (final-day snapshot).
"""

import random
import numpy as np
from datetime import timedelta
from collections import defaultdict
import writers


# ─── ID generators ────────────────────────────────────────────────────────────

class _Seq:
    """Simple thread-unsafe sequential counter."""
    def __init__(self):
        self._n = 0

    def next(self):
        self._n += 1
        return self._n


def run_simulation(cfg, md, dates, demand_array, feeds_dir):
    """
    cfg          : CONFIG dict
    md           : MasterData
    dates        : list of date objects (simulation horizon)
    demand_array : int32 numpy array shape (n_stores, n_items, n_days)
    feeds_dir    : output directory path string
    """
    rng = random.Random(cfg["seed"] + 99)
    run_id   = cfg["run_id"]
    scenario = cfg["scenario"]

    n_stores = len(md.store_codes)
    n_items  = len(md.item_codes)

    # ── Index maps ────────────────────────────────────────────────────────────
    store_idx = {code: i for i, code in enumerate(md.store_codes)}
    item_idx  = {code: i for i, code in enumerate(md.item_codes)}
    dc_code   = md.dc_codes[0]   # single DC

    # ── Inventory state (int arrays) ──────────────────────────────────────────
    # on_hand[0..n_stores-1] = stores, [n_stores] = DC
    DC_IDX = n_stores
    n_nodes = n_stores + 1

    # Estimate avg daily demand per item (across all stores) for init stock
    avg_daily = demand_array.mean(axis=(0, 2))   # shape (n_items,)

    # DC initial stock
    dc_init_days  = cfg["dc_init_coverage_days"]
    store_init_days = cfg["store_init_coverage_days"]

    on_hand = np.zeros((n_nodes, n_items), dtype=np.int64)
    on_hand[DC_IDX, :] = np.maximum(
        np.round(avg_daily * dc_init_days * n_stores).astype(np.int64), 0
    )
    for si in range(n_stores):
        on_hand[si, :] = np.maximum(
            np.round(avg_daily * store_init_days).astype(np.int64), 0
        )

    on_order_dc = np.zeros(n_items, dtype=np.int64)

    # ── Receipt event queue: date_str → list of receipt dicts ─────────────────
    receipt_events = defaultdict(list)   # date → [event, ...]
    # event keys: po_number, po_line, item_idx, qty_due, supplier_code

    # ── Sequence counters ─────────────────────────────────────────────────────
    seq_po  = _Seq()
    seq_grv = _Seq()
    seq_dn  = _Seq()
    seq_co  = _Seq()

    # ── Accumulators (lists of row dicts written incrementally) ───────────────
    rows_soh  = []   # SupplierOrderHeader
    rows_sol  = []   # SupplierOrderLine
    rows_sr   = []   # SupplierReceipts
    rows_coh  = []   # CustomerOrderHeader
    rows_col  = []   # CustomerOrderLine
    rows_cod  = []   # CustomerOrderDelivery
    rows_sales= []   # SalesHistoryByType
    rows_inv  = []   # Inventory snapshot (final day only)

    # Track outstanding qty per PO line (for status updates)
    # po_outstanding[(po_number, po_line)] = int
    po_outstanding = {}

    # For inventory reconciliation verification (optional, lightweight)
    # last_on_hand[node_idx, item_idx] = qty at end of previous day
    last_on_hand = on_hand.copy()

    # ── Config shortcuts ──────────────────────────────────────────────────────
    cov_days     = cfg["store_coverage_days"]
    dc_cov_days  = cfg["dc_coverage_days"]
    smooth_win   = cfg["demand_smoothing_window"]
    review_dow   = cfg["dc_review_dow"]   # 0=Monday
    p_late       = cfg["p_late"]
    late_min     = cfg["late_days_min"]
    late_max     = cfg["late_days_max"]
    p_partial    = cfg["p_partial"]
    pfrac_min    = cfg["partial_frac_min"]
    pfrac_max    = cfg["partial_frac_max"]
    rgap_min     = cfg["remainder_gap_min"]
    rgap_max     = cfg["remainder_gap_max"]
    base_currency = cfg["base_currency"]

    date_to_idx = {d: i for i, d in enumerate(dates)}
    n_days = len(dates)

    print(f"\n  Simulating {n_days} days ({dates[0]} → {dates[-1]}) ...")

    for day_num, D in enumerate(dates):
        D_str  = writers.fmt_date(D)
        D_date = D   # already a date object

        # ── Step 1: Post supplier receipts into DC ────────────────────────────
        events_today = receipt_events.pop(D, [])
        for evt in events_today:
            i_item     = evt["item_idx"]
            qty_due    = evt["qty_due"]
            po_num     = evt["po_number"]
            po_line    = evt["po_line"]
            supplier   = evt["supplier_code"]

            # Late / partial roll
            actually_late = rng.random() < p_late
            if actually_late:
                late_days = rng.randint(late_min, late_max)
                late_date = D + timedelta(days=late_days)
                # Reschedule entire event
                evt["qty_due"] = qty_due
                receipt_events[late_date].append(evt)
                continue

            actually_partial = rng.random() < p_partial
            if actually_partial:
                frac = rng.uniform(pfrac_min, pfrac_max)
                now_qty = max(1, round(qty_due * frac))
                remainder = qty_due - now_qty
                gap = rng.randint(rgap_min, rgap_max)
                remainder_date = D + timedelta(days=gap)
                # Schedule remainder
                receipt_events[remainder_date].append({
                    "po_number":    po_num,
                    "po_line":      po_line,
                    "item_idx":     i_item,
                    "qty_due":      remainder,
                    "supplier_code": supplier,
                })
                recv_qty = now_qty
            else:
                recv_qty = qty_due

            # Update DC stock
            on_hand[DC_IDX, i_item] += recv_qty
            on_order_dc[i_item]     = max(0, on_order_dc[i_item] - recv_qty)

            # Update PO outstanding
            key = (po_num, po_line)
            if key in po_outstanding:
                po_outstanding[key] = max(0, po_outstanding[key] - recv_qty)

            grv_num = f"GRV_{run_id}_{seq_grv.next():06d}"
            item_code_str = md.item_codes[i_item]
            rows_sr.append({
                "GRVNumber":              grv_num,
                "PurchaseOrderNumber":    po_num,
                "SiteCode":               dc_code,
                "ItemCode":               item_code_str,
                "ReceivedQuantity":       recv_qty,
                "ActualReceiptDate":      D_str,
                "IBTSourceSite":          "",       # from supplier, not IBT
                "SupplierCode":           supplier,
                "PurchaseOrderLineNumber": po_line,
                "TotalCost":              round(recv_qty * md.item_cost_price[item_code_str], 2),
                "ReceiptCurrencyCode":    base_currency,
            })

        # ── Step 2: Create customer orders ────────────────────────────────────
        for si, store_code in enumerate(md.store_codes):
            co_num = f"CO_{run_id}_{D.strftime('%Y%m%d')}_{store_code}_{seq_co.next():04d}"
            has_lines = False
            line_num = 0

            for i_item in range(n_items):
                req = int(demand_array[si, i_item, day_num])
                if req <= 0:
                    continue
                if not has_lines:
                    # Write header on first line
                    rows_coh.append({
                        "CustomerOrderNumber":   co_num,
                        "CustomerOrderDate":     D_str,
                        "IBTFlag":               0,
                        "OrderStatusIndicator":  "Placed",
                    })
                    has_lines = True

                line_num += 1
                item_code_str = md.item_codes[i_item]
                rows_col.append({
                    "CustomerOrderNumber":     co_num,
                    "CustomerOrderLineNumber": line_num,
                    "SiteCode":               store_code,
                    "ItemCode":               item_code_str,
                    "EstimatedDeliveryDate":  D_str,
                    "OrderedQuantity":        req,
                    "OrderLineStatusIndicator": "Placed",
                    "IBTDestinationSiteCode": "",
                    "OutstandingQuantity":    req,
                })

        # ── Step 3: Compute store replenishment needs ─────────────────────────
        # moving_avg over last smooth_win days of demand
        win_start = max(0, day_num - smooth_win + 1)
        # avg_store_demand: shape (n_stores, n_items)
        avg_store_demand = demand_array[:, :, win_start:day_num + 1].mean(axis=2)

        store_needs = np.zeros((n_stores, n_items), dtype=np.int64)
        for i_item in range(n_items):
            velocity = md.item_velocity[md.item_codes[i_item]]
            cov = cov_days[velocity]
            for si in range(n_stores):
                target = avg_store_demand[si, i_item] * cov
                need = int(max(0, round(target - on_hand[si, i_item])))
                store_needs[si, i_item] = need

        # ── Step 4: Allocate DC→store shipments (IBTs) ────────────────────────
        dc_shipments = np.zeros((n_stores, n_items), dtype=np.int64)

        for i_item in range(n_items):
            need_sum = int(store_needs[:, i_item].sum())
            if need_sum == 0:
                continue
            avail = int(on_hand[DC_IDX, i_item])
            if avail == 0:
                continue

            if avail >= need_sum:
                ship_per_store = store_needs[:, i_item].copy()
            else:
                # Proportional allocation
                proportional = avail * store_needs[:, i_item] / need_sum
                ship_per_store = np.floor(proportional).astype(np.int64)
                remainder = avail - int(ship_per_store.sum())
                if remainder > 0:
                    # Distribute remainder to stores with largest fractional part
                    fracs = proportional - ship_per_store
                    top_stores = np.argsort(fracs)[::-1][:remainder]
                    ship_per_store[top_stores] += 1

            dc_shipments[:, i_item] = ship_per_store

        # Write IBT PO records (one header + line per store that receives stock)
        ibt_total = int(dc_shipments.sum())
        if ibt_total > 0:
            for si, store_code in enumerate(md.store_codes):
                store_total = int(dc_shipments[si, :].sum())
                if store_total == 0:
                    continue
                po_num = f"PO_{run_id}_{D.strftime('%Y%m%d')}_{dc_code}_IBT_{seq_po.next():06d}"
                rows_soh.append({
                    "PurchaseOrderNumber":  po_num,
                    "PurchaseOrderDate":    D_str,
                    "IBTFlag":              1,
                    "SupplierOrderStatus":  "Delivered",
                    "ReceiveNoLaterThan":   D_str,   # same-day arrival
                })
                line_n = 0
                for i_item in range(n_items):
                    ship_qty = int(dc_shipments[si, i_item])
                    if ship_qty == 0:
                        continue
                    line_n += 1
                    item_code_str = md.item_codes[i_item]
                    rows_sol.append({
                        "PurchaseOrderNumber":     po_num,
                        "PurchaseOrderLineNumber": line_n,
                        "SiteCode":               store_code,
                        "ItemCode":               item_code_str,
                        "EstimatedReceiptDate":   D_str,
                        "OrderedQuantity":        ship_qty,
                        "OrderLineStatusIndicator": "Delivered",
                        "SupplierCode":           "",       # IBT — no supplier
                        "CurrencyCode":           base_currency,
                        "IBTSiteCode":            dc_code,
                        "OutstandingQuantity":    0,
                        "CostPerUnit":            round(md.item_cost_price[item_code_str], 2),
                    })

        # Update inventory for shipments (same-day arrival)
        shipped_per_item = dc_shipments.sum(axis=0)   # (n_items,)
        on_hand[DC_IDX, :] -= shipped_per_item
        for si in range(n_stores):
            on_hand[si, :] += dc_shipments[si, :]

        # Safety: clamp DC non-negative (should never trigger)
        np.clip(on_hand, 0, None, out=on_hand)

        # ── Step 5: Fulfill deliveries at stores ──────────────────────────────
        # We need to match back to CO lines we wrote above.
        # Simplified: one delivery note per store per day (covers all delivered items).
        for si, store_code in enumerate(md.store_codes):
            dn_num = f"DN_{run_id}_{D.strftime('%Y%m%d')}_{store_code}_{seq_dn.next():06d}"
            has_delivery = False
            line_n = 0

            # The CO number for this store/day is the one written in Step 2.
            # Rather than look it up, we embed store+date in the CO pattern.
            co_num = f"CO_{run_id}_{D.strftime('%Y%m%d')}_{store_code}"
            # Note: seq suffix varies — we just use the store+date prefix to
            # associate deliveries; the CO header writer uses the same prefix.

            for i_item in range(n_items):
                req = int(demand_array[si, i_item, day_num])
                if req <= 0:
                    continue
                avail_store = int(on_hand[si, i_item])
                deliv = min(req, avail_store)
                if deliv <= 0:
                    continue

                on_hand[si, i_item] -= deliv
                line_n += 1
                item_code_str = md.item_codes[i_item]

                # Find the corresponding CO number (match store+date prefix)
                matching_co = next(
                    (r["CustomerOrderNumber"] for r in reversed(rows_coh)
                     if r["CustomerOrderNumber"].startswith(co_num)),
                    co_num + "_0001"
                )

                rows_cod.append({
                    "DeliveryNoteNumber":      dn_num,
                    "CustomerOrderNumber":     matching_co,
                    "SiteCode":               store_code,
                    "ItemCode":               item_code_str,
                    "DeliveredQuantity":       deliv,
                    "ActualDeliveryDate":      D_str,
                    "CustomerOrderLineNumber": line_n,
                })

                has_delivery = True

                # ── Step 6: Write sales (sales = delivered) ───────────────────
                sell_p = md.item_sell_price[item_code_str]
                cost_p = md.item_cost_price[item_code_str]
                rows_sales.append({
                    "SiteCode":          store_code,
                    "ItemCode":          item_code_str,
                    "SalesTypeCode":     "Regular",
                    "ReturnFlag":        0,
                    "SalesDate":         D_str,
                    "SalesQuantity":     deliv,
                    "TotalCost":         round(deliv * cost_p, 2),
                    "TotalRevenue":      round(deliv * sell_p, 2),
                    "TotalOriginalRetail": round(deliv * sell_p, 2),
                })

        # ── Step 7: DC supplier PO review (Mondays only) ──────────────────────
        if D.weekday() == review_dow:
            # DC avg daily demand = sum of store smoothed demands
            dc_avg_daily = avg_store_demand.sum(axis=0)   # (n_items,)

            for i_item in range(n_items):
                item_code_str = md.item_codes[i_item]
                supplier_code = md.item_supplier[item_code_str]
                lead_days = md.supplier_lead_time[supplier_code]

                target_dc  = dc_avg_daily[i_item] * dc_cov_days
                inv_pos    = int(on_hand[DC_IDX, i_item]) + int(on_order_dc[i_item])
                order_qty  = int(max(0, round(target_dc - inv_pos)))

                if order_qty <= 0:
                    continue

                po_num  = f"PO_{run_id}_{D.strftime('%Y%m%d')}_{dc_code}_{seq_po.next():06d}"
                po_line = 1
                eta     = D + timedelta(days=lead_days)
                eta_str = writers.fmt_date(eta)

                rows_soh.append({
                    "PurchaseOrderNumber":  po_num,
                    "PurchaseOrderDate":    D_str,
                    "IBTFlag":              0,
                    "SupplierOrderStatus":  "Placed",
                    "ReceiveNoLaterThan":   eta_str,
                })
                rows_sol.append({
                    "PurchaseOrderNumber":     po_num,
                    "PurchaseOrderLineNumber": po_line,
                    "SiteCode":               dc_code,
                    "ItemCode":               item_code_str,
                    "EstimatedReceiptDate":   eta_str,
                    "OrderedQuantity":        order_qty,
                    "OrderLineStatusIndicator": "Placed",
                    "SupplierCode":           supplier_code,
                    "CurrencyCode":           base_currency,
                    "IBTSiteCode":            "",
                    "OutstandingQuantity":    order_qty,
                    "CostPerUnit":            round(md.item_cost_price[item_code_str], 2),
                })
                po_outstanding[(po_num, po_line)] = order_qty

                # Schedule receipt event
                receipt_events[eta].append({
                    "po_number":    po_num,
                    "po_line":      po_line,
                    "item_idx":     i_item,
                    "qty_due":      order_qty,
                    "supplier_code": supplier_code,
                })
                on_order_dc[i_item] += order_qty

        last_on_hand = on_hand.copy()

    # ── Step 8: Write final-day inventory snapshot ────────────────────────────
    # Spec: Inventory.txt is a point-in-time snapshot (no InventoryDate column)
    first_stocked = writers.fmt_date(dates[0])
    for si, site_code in enumerate(md.store_codes + md.dc_codes):
        node_idx = si if si < n_stores else DC_IDX
        for i_item, item_code_str in enumerate(md.item_codes):
            soh = int(on_hand[node_idx, i_item])
            supplier_code = md.item_supplier[item_code_str]
            is_dc = (site_code in md.dc_codes)
            rows_inv.append({
                "SiteCode":           site_code,
                "ItemCode":           item_code_str,
                "FirstStockedDate":   first_stocked,
                "StockOnHand":        soh,
                "StockReserved":      0,
                "DefaultCostPrice":   md.item_cost_price[item_code_str],
                "DefaultSellingPrice": md.item_sell_price[item_code_str],
                "SupplierCode":       supplier_code,
                "SourceSite":         dc_code if not is_dc else "",
                "FromSupplierFlag":   0 if not is_dc else 1,
                "StockingIndicator":  "Y",
                "OrderMultiple":      1,
                "ActiveFlag":         1,
            })

    # ── Write all feeds ───────────────────────────────────────────────────────
    _write_all(feeds_dir, rows_soh, rows_sol, rows_sr,
               rows_coh, rows_col, rows_cod, rows_sales, rows_inv)


def _write_all(feeds_dir,
               rows_soh, rows_sol, rows_sr,
               rows_coh, rows_col, rows_cod, rows_sales, rows_inv):
    feed_map = [
        ("SupplierOrderHeader.txt",   rows_soh,   writers.SUPPLIER_ORDER_HEADER_COLUMNS),
        ("SupplierOrderLine.txt",     rows_sol,   writers.SUPPLIER_ORDER_LINE_COLUMNS),
        ("SupplierReceipts.txt",      rows_sr,    writers.SUPPLIER_RECEIPTS_COLUMNS),
        ("CustomerOrderHeader.txt",   rows_coh,   writers.CUSTOMER_ORDER_HEADER_COLUMNS),
        ("CustomerOrderLine.txt",     rows_col,   writers.CUSTOMER_ORDER_LINE_COLUMNS),
        ("CustomerOrderDelivery.txt", rows_cod,   writers.CUSTOMER_ORDER_DELIVERY_COLUMNS),
        ("SalesHistoryByType.txt",    rows_sales, writers.SALES_HISTORY_COLUMNS),
        ("Inventory.txt",             rows_inv,   writers.INVENTORY_COLUMNS),
    ]
    for filename, rows, columns in feed_map:
        writers.write_feed(f"{feeds_dir}/{filename}", rows, columns)
        print(f"  {filename:<30} — {len(rows):>8,} rows")
