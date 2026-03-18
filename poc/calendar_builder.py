"""
Builds CalendarPeriod.txt and CurrencyTemporal.txt.

CalendarPeriod rows:
  - One row per Week  (PeriodType=Week,    PeriodOfYear=1-52, parent=Month)
  - One row per Month (PeriodType=Month,   PeriodOfYear=1-12, parent=Quarter)
  - One row per Quarter (PeriodType=Quarter, PeriodOfYear=1-4, parent=Year)
  - One row per Year  (PeriodType=Year,    PeriodOfYear=<year>, parent="")

CalendarName = "Standard" for all rows.
"""

from datetime import date, timedelta
import writers


def build_calendar(start_date, end_date, feeds_dir):
    """
    Generate CalendarPeriod.txt covering all weeks/months/quarters/years
    that overlap with [start_date, end_date].
    """
    rows = []
    calendar_name = "Standard"

    # ── Collect all ISO weeks in the range ────────────────────────────────────
    # Walk day-by-day and collect unique ISO (year, week) pairs
    seen_weeks = {}   # (iso_year, iso_week) -> (week_start, week_end)
    seen_months = {}  # (year, month) -> (month_start, month_end)
    seen_quarters = {}  # (year, quarter) -> (q_start, q_end)
    seen_years = {}   # year -> (year_start, year_end)

    d = start_date
    while d <= end_date:
        iso = d.isocalendar()           # (iso_year, iso_week, iso_weekday)
        yw = (iso[0], iso[1])
        if yw not in seen_weeks:
            # Week start = Monday of that ISO week
            week_start = d - timedelta(days=d.weekday())
            week_end   = week_start + timedelta(days=6)
            seen_weeks[yw] = (week_start, week_end)

        ym = (d.year, d.month)
        if ym not in seen_months:
            m_start = date(d.year, d.month, 1)
            # Last day of month
            if d.month == 12:
                m_end = date(d.year, 12, 31)
            else:
                m_end = date(d.year, d.month + 1, 1) - timedelta(days=1)
            seen_months[ym] = (m_start, m_end)

        q = (d.month - 1) // 3 + 1
        yq = (d.year, q)
        if yq not in seen_quarters:
            q_month_start = (q - 1) * 3 + 1
            q_start = date(d.year, q_month_start, 1)
            q_end_month = q_month_start + 2
            if q_end_month == 12:
                q_end = date(d.year, 12, 31)
            else:
                q_end = date(d.year, q_end_month + 1, 1) - timedelta(days=1)
            seen_quarters[yq] = (q_start, q_end)

        if d.year not in seen_years:
            seen_years[d.year] = (date(d.year, 1, 1), date(d.year, 12, 31))

        d += timedelta(days=1)

    # ── Year rows ─────────────────────────────────────────────────────────────
    for year, (y_start, y_end) in sorted(seen_years.items()):
        rows.append({
            "PeriodType":       "Year",
            "PeriodOfYear":     year,
            "PeriodName":       f"YR_{year}",
            "StartDate":        writers.fmt_date(y_start),
            "EndDate":          writers.fmt_date(y_end),
            "ParentPeriodName": "",
            "CalendarName":     calendar_name,
        })

    # ── Quarter rows ──────────────────────────────────────────────────────────
    for (year, q), (q_start, q_end) in sorted(seen_quarters.items()):
        rows.append({
            "PeriodType":       "Quarter",
            "PeriodOfYear":     q,
            "PeriodName":       f"Q{q}_{year}",
            "StartDate":        writers.fmt_date(q_start),
            "EndDate":          writers.fmt_date(q_end),
            "ParentPeriodName": f"YR_{year}",
            "CalendarName":     calendar_name,
        })

    # ── Month rows ────────────────────────────────────────────────────────────
    month_names = ["Jan","Feb","Mar","Apr","May","Jun",
                   "Jul","Aug","Sep","Oct","Nov","Dec"]
    for (year, month), (m_start, m_end) in sorted(seen_months.items()):
        q = (month - 1) // 3 + 1
        rows.append({
            "PeriodType":       "Month",
            "PeriodOfYear":     month,
            "PeriodName":       f"{month_names[month-1]}_{year}",
            "StartDate":        writers.fmt_date(m_start),
            "EndDate":          writers.fmt_date(m_end),
            "ParentPeriodName": f"Q{q}_{year}",
            "CalendarName":     calendar_name,
        })

    # ── Week rows ─────────────────────────────────────────────────────────────
    for (iso_year, iso_week), (w_start, w_end) in sorted(seen_weeks.items()):
        # Parent month = whichever month the week's Thursday falls in (ISO convention)
        thursday = w_start + timedelta(days=3)
        parent_month = f"{month_names[thursday.month-1]}_{thursday.year}"
        rows.append({
            "PeriodType":       "Week",
            "PeriodOfYear":     iso_week,
            "PeriodName":       f"WK_{iso_week}_{iso_year}",
            "StartDate":        writers.fmt_date(w_start),
            "EndDate":          writers.fmt_date(w_end),
            "ParentPeriodName": parent_month,
            "CalendarName":     calendar_name,
        })

    filepath = f"{feeds_dir}/CalendarPeriod.txt"
    writers.write_feed(filepath, rows, writers.CALENDAR_PERIOD_COLUMNS)
    print(f"  CalendarPeriod.txt   — {len(rows)} rows")
    return rows


def build_currency(base_currency, start_date, end_date, feeds_dir):
    """
    Generate CurrencyTemporal.txt.
    Single entry: base_currency → base_currency at rate 1.0 (self-conversion).
    """
    rows = [
        {
            "CurrencyCodeFrom": base_currency,
            "CurrencyCodeTo":   base_currency,
            "StartDate":        writers.fmt_date(start_date),
            "EndDate":          writers.fmt_date(end_date),
            "ConversionRate":   1.0,
        }
    ]
    filepath = f"{feeds_dir}/CurrencyTemporal.txt"
    writers.write_feed(filepath, rows, writers.CURRENCY_COLUMNS)
    print(f"  CurrencyTemporal.txt — {len(rows)} rows")
    return rows
