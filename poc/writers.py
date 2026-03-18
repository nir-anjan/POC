"""
Feed writers — exact column contracts per JustEnough spec v3.6.2.
Delimiter: pipe (|). Date format: YYYY-MM-DD 00:00:00.
"""

import csv
import os
from datetime import datetime, date


# ── Helpers ────────────────────────────────────────────────────────────────────

def fmt_date(d):
    """Format a date/datetime to JustEnough datetime format."""
    if d is None:
        return ""
    if isinstance(d, datetime):
        return d.strftime("%Y-%m-%d 00:00:00")
    if isinstance(d, date):
        return datetime(d.year, d.month, d.day).strftime("%Y-%m-%d 00:00:00")
    return str(d)


def write_feed(filepath, rows, columns):
    """
    Write a pipe-delimited feed file.
    rows: list of dicts keyed by column name.
    columns: ordered list of column names (defines output column order).
    Missing keys → empty string.
    """
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter="|", quoting=csv.QUOTE_NONE, escapechar="\\")
        writer.writerow(columns)
        for row in rows:
            writer.writerow([row.get(c, "") for c in columns])


# ══════════════════════════════════════════════════════════════════════════════
# Column contracts — exact field names and order per spec
# ══════════════════════════════════════════════════════════════════════════════

# ── Site.txt ───────────────────────────────────────────────────────────────────
SITE_COLUMNS = [
    "SiteCode", "CurrencyCode", "SiteName", "CountryCode",
    "SiteStatus", "HostSystemLeadTime", "SiteRegion", "SiteType",
]

# ── ItemMaster.txt ─────────────────────────────────────────────────────────────
ITEM_COLUMNS = [
    "ItemCode", "ProductDescription", "ExternalItemMasterID",
    "SizeName", "SizeTypeName", "StyleCode", "ColorCode", "VariantCode",
    "ActiveFlag",
]

# ── Supplier.txt ───────────────────────────────────────────────────────────────
SUPPLIER_COLUMNS = [
    "SupplierCode", "SupplierName", "HostSystemLeadTime", "SupplierActiveFlag",
]

# ── Inventory.txt ──────────────────────────────────────────────────────────────
INVENTORY_COLUMNS = [
    "SiteCode", "ItemCode", "FirstStockedDate", "StockOnHand", "StockReserved",
    "DefaultCostPrice", "DefaultSellingPrice", "SupplierCode",
    "SourceSite", "FromSupplierFlag", "StockingIndicator", "OrderMultiple",
    "ActiveFlag",
]

# ── SupplierOrderHeader.txt ────────────────────────────────────────────────────
SUPPLIER_ORDER_HEADER_COLUMNS = [
    "PurchaseOrderNumber", "PurchaseOrderDate", "IBTFlag",
    "SupplierOrderStatus", "ReceiveNoLaterThan",
]

# ── SupplierOrderLine.txt ──────────────────────────────────────────────────────
SUPPLIER_ORDER_LINE_COLUMNS = [
    "PurchaseOrderNumber", "PurchaseOrderLineNumber", "SiteCode", "ItemCode",
    "EstimatedReceiptDate", "OrderedQuantity", "OrderLineStatusIndicator",
    "SupplierCode", "CurrencyCode", "IBTSiteCode", "OutstandingQuantity",
    "CostPerUnit",
]

# ── SupplierReceipts.txt ───────────────────────────────────────────────────────
SUPPLIER_RECEIPTS_COLUMNS = [
    "GRVNumber", "PurchaseOrderNumber", "SiteCode", "ItemCode",
    "ReceivedQuantity", "ActualReceiptDate", "IBTSourceSite", "SupplierCode",
    "PurchaseOrderLineNumber", "TotalCost", "ReceiptCurrencyCode",
]

# ── CustomerOrderHeader.txt ────────────────────────────────────────────────────
CUSTOMER_ORDER_HEADER_COLUMNS = [
    "CustomerOrderNumber", "CustomerOrderDate", "IBTFlag", "OrderStatusIndicator",
]

# ── CustomerOrderLine.txt ──────────────────────────────────────────────────────
CUSTOMER_ORDER_LINE_COLUMNS = [
    "CustomerOrderNumber", "CustomerOrderLineNumber", "SiteCode", "ItemCode",
    "EstimatedDeliveryDate", "OrderedQuantity", "OrderLineStatusIndicator",
    "IBTDestinationSiteCode", "OutstandingQuantity",
]

# ── CustomerOrderDelivery.txt ──────────────────────────────────────────────────
CUSTOMER_ORDER_DELIVERY_COLUMNS = [
    "DeliveryNoteNumber", "CustomerOrderNumber", "SiteCode", "ItemCode",
    "DeliveredQuantity", "ActualDeliveryDate", "CustomerOrderLineNumber",
]

# ── SalesHistoryByType.txt ─────────────────────────────────────────────────────
SALES_HISTORY_COLUMNS = [
    "SiteCode", "ItemCode", "SalesTypeCode", "ReturnFlag", "SalesDate",
    "SalesQuantity", "TotalCost", "TotalRevenue", "TotalOriginalRetail",
]

# ── DailyScenarioTrace.txt (story diagnostics) ───────────────────────────────
DAILY_SCENARIO_TRACE_COLUMNS = [
    "Date", "SiteCode", "ItemCode", "StockBefore", "Demand", "Delivered",
    "UnmetDemand", "StockLeft", "DCShipQty", "RuleLabel",
]

# ── CalendarPeriod.txt ─────────────────────────────────────────────────────────
CALENDAR_PERIOD_COLUMNS = [
    "PeriodType", "PeriodOfYear", "PeriodName", "StartDate", "EndDate",
    "ParentPeriodName", "CalendarName",
]

# ── CurrencyTemporal.txt ───────────────────────────────────────────────────────
CURRENCY_COLUMNS = [
    "CurrencyCodeFrom", "CurrencyCodeTo", "StartDate", "EndDate", "ConversionRate",
]

# ── ItemMasterGroup1/2/3.txt ───────────────────────────────────────────────────
ITEM_MASTER_GROUP1_COLUMNS = ["ItemMasterGroup1Code", "ItemMasterGroup1Description"]
ITEM_MASTER_GROUP2_COLUMNS = ["ItemMasterGroup2Code", "ItemMasterGroup2Description"]
ITEM_MASTER_GROUP3_COLUMNS = ["ItemMasterGroup3Code", "ItemMasterGroup3Description"]

# ── ItemMasterGroup.txt (link table) ──────────────────────────────────────────
ITEM_MASTER_GROUP_DETAIL_COLUMNS = [
    "ItemCode",
    "ItemMasterGroup1Code", "ItemMasterGroup2Code", "ItemMasterGroup3Code",
]

# ── SiteGroup1.txt / SiteGroup2.txt ───────────────────────────────────────────
SITE_GROUP1_COLUMNS = ["SiteGroup1Code", "SiteGroup1Description"]
SITE_GROUP2_COLUMNS = ["SiteGroup2Code", "SiteGroup2Description"]
