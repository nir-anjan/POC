# Clothing Industry Synthetic Data Generator

A pre-MVP synthetic data generator for a clothing retail supply chain.

It produces a small but internally consistent demo dataset for a JustEnough-style feed contract, with demand flowing through:

- customer orders at stores
- inventory-constrained deliveries and sales
- DC-to-store replenishment
- supplier-to-DC purchase orders and receipts
- final inventory snapshots

The project is intentionally simple:

- no CLI
- no YAML config
- no database
- no API
- one Python entry point
- deterministic output from a fixed seed

## What It Generates

The generator builds two parallel output formats for the same run:

- pipe-delimited TXT feeds
- Excel copies of the same feeds

Output structure:

```text
output/<run_id>_<scenario>/
  feeds_txt/
    calendar and currency feeds/
    master data feeds/
    simulation feeds/
  feeds_excel/
    calendar and currency feeds/
    master data feeds/
    simulation feeds/
  run_manifest.json
```

Current feed groups:

### Calendar and currency feeds
- `CalendarPeriod.txt`
- `CurrencyTemporal.txt`

### Master data feeds
- `Site.txt`
- `Supplier.txt`
- `ItemMaster.txt`
- `ItemMasterGroup1.txt`
- `ItemMasterGroup2.txt`
- `ItemMasterGroup3.txt`
- `ItemMasterGroup.txt`
- `SiteGroup1.txt`
- `SiteGroup2.txt`

### Simulation feeds
- `SupplierOrderHeader.txt`
- `SupplierOrderLine.txt`
- `SupplierReceipts.txt`
- `CustomerOrderHeader.txt`
- `CustomerOrderLine.txt`
- `CustomerOrderDelivery.txt`
- `SalesHistoryByType.txt`
- `Inventory.txt`

## Current Demo Scope

The current config is set to a very small demo dataset for fast testing:

- 2 stores
- 1 DC
- 5 items
- 3 suppliers
- 4 weeks of history
- base currency: USD

Scenarios:

- `summer`
- `winter`

The scenario changes:

- the simulation start date
- the seasonal demand profile used for item categories

## How to Run

From the `poc` folder:

```bash
python run.py
```

If Excel export dependencies are missing:

```bash
pip install pandas openpyxl
```

## Determinism

The generator is deterministic when these remain unchanged:

- `seed`
- `scenario`
- configuration values
- code version
- Python and package versions

Random generators are seeded separately by stage:

- master data generation
- demand generation
- simulation behavior

That means the same inputs should produce the same outputs.

## End-to-End Data Flow

The execution order is controlled by `poc/run.py`:

1. Resolve run dates from the selected scenario
2. Build calendar and currency feeds
3. Build master data and group feeds
4. Build the demand matrix
5. Run the daily simulation engine
6. Convert TXT feeds to Excel copies
7. Write `run_manifest.json`

In simple terms:

```text
config -> master data -> demand matrix -> daily simulation -> feeds -> excel copies
```

## Core Modules

## `poc/config.py`
Central configuration object.

It defines:

- run ID
- seed
- scenario
- scale
- history length
- currency
- clothing categories
- price ranges
- base demand ranges
- seasonal profiles
- weekend uplift rules
- receipt randomness
- replenishment settings
- initial inventory coverage

This file is the main input to the whole generator.

## `poc/master_data.py`
Builds the static reference data used by the rest of the system.

It creates:

- sites
- suppliers
- items
- group feeds

### Site generation logic
- Creates DCs first, then stores
- Assigns each store a region from the configured region list
- Sets site type as `DC` or `Store`

### Supplier generation logic
- Creates synthetic supplier codes like `SUP_001`
- Assigns a lead time per supplier using the configured lead time range

### Item generation logic
For each configured category, it creates items with:

- item code
- product description
- size
- size type
- style code
- color
- variant code
- selling price
- cost price
- velocity class
- seasonal profile
- primary supplier

It also returns a `MasterData` object used by later stages.

That object carries the in-memory lookup tables the simulator relies on:

- item list
- store list
- DC list
- supplier list
- item to supplier mapping
- item velocity
- item category
- item seasonal profile
- item selling price
- item cost price
- supplier lead times
- site region and type

## `poc/calendar_builder.py`
Builds the time and currency dimensions.

### Calendar logic
It scans the requested date range and creates period rows for:

- Year
- Quarter
- Month
- Week

Each period has:

- name
- start date
- end date
- parent period name
- calendar name

This creates the planning hierarchy required by the feed format.

### Currency logic
Creates a single self-conversion row:

- `USD -> USD` with rate `1.0`

This keeps the model simple while still satisfying the expected feed contract.

## `poc/demand.py`
This file builds the demand matrix.

This is the core synthetic demand signal used by the simulator.

The output is a 3D numpy array:

```text
[store, item, day]
```

Each cell is the requested quantity for one store, one item, on one day.

## How the demand matrix is made

For each item:

1. Determine its velocity class
2. Determine its seasonal profile
3. Draw a base mean demand from the configured range for that velocity
4. Build a daily seasonal multiplier across the full date horizon
5. Apply weekend uplift where configured
6. Generate random daily demand from a Poisson distribution
7. Apply lumpy spike logic for lumpy items
8. Apply rare outlier spikes
9. Apply a mild per-store scaling factor
10. Round to integers and clamp at zero

### Velocity logic
Velocity controls the base daily demand range:

- fast items have higher baseline demand
- medium items have moderate demand
- slow items have low demand
- lumpy items have mostly zero demand with occasional spikes

### Seasonal logic
Each category maps to a seasonal profile such as:

- `flat`
- `summer`
- `mild`
- `winter`
- `strongwinter`
- `holiday`
- `formalholiday`

Those profiles define:

- which ISO weeks are peak weeks
- peak multiplier
- off-peak multiplier

The selected scenario decides which profile branch is used.

Example:

- in `summer`, tops get boosted during summer weeks
- in `winter`, outerwear gets boosted during winter weeks

### Weekend logic
Fast and medium items receive a Friday/Saturday uplift.

This is intended to mimic stronger weekend trading patterns.

### Lumpy demand logic
Lumpy items behave differently:

- most days are zero
- some days spike sharply

This is modeled with a spike probability and spike multiplier.

### Outlier logic
All items can receive rare outlier spikes.

This adds occasional abnormal demand bursts.

## How the demand matrix is used

The demand matrix is not written directly to a feed.

Instead, it becomes the source of truth for store requested demand inside the simulator.

For each day:

- the simulator reads `demand[store, item, day]`
- creates customer order lines for positive demand
- tries to fulfill that demand from store on-hand inventory
- writes deliveries and sales based on what could actually be fulfilled

So the demand matrix is the upstream driver of:

- customer orders
- deliveries
- sales
- replenishment need
- supplier PO creation indirectly through DC inventory pressure

## `poc/simulation.py`
This is the B1 simulation engine.

It models this network:

```text
Supplier -> DC -> Store -> Customer
```

It runs one day at a time across the date horizon.

## Simulation state
The simulation maintains in-memory state for:

- on-hand inventory at each store
- on-hand inventory at the DC
- open supplier orders to the DC
- scheduled future receipt events

## Initial inventory logic
Before the loop starts:

- DC stock is initialized to about 30 days of average item demand across stores
- store stock is initialized to about 5 days of average item demand

This prevents the system from immediately collapsing into stockouts on day one.

## Daily simulation order
The simulator follows this order each day.

### 1. Post supplier receipts into DC
The engine checks whether any receipt events are scheduled for the current day.

For each receipt event:

- it may be delayed with probability `p_late`
- it may be partially received with probability `p_partial`
- remainders are rescheduled into the future
- received quantity increases DC on-hand
- open on-order quantity is reduced
- receipt rows are written to `SupplierReceipts.txt`

This is how lead-time uncertainty enters the system.

### 2. Create customer orders
For each store and item with positive requested demand that day:

- create a customer order header for the store-day if needed
- create customer order lines for items with demand

These rows represent customer requested demand, not necessarily fulfilled demand.

### 3. Compute store replenishment need
For each store-item pair:

- compute a moving average demand over the configured smoothing window
- multiply by coverage days for that velocity class
- compare target stock to current on-hand
- need is `max(0, target - on_hand)`

This creates a replenishment request from the store side.

### 4. Allocate DC to store shipments
For each item:

- sum total store need
- compare with DC available inventory
- if DC has enough, fill all needs
- if DC is constrained, allocate proportionally
- distribute remaining units to stores with the largest fractional need

Then:

- DC on-hand decreases
- store on-hand increases the same day
- inter-branch transfer rows are written as supplier order header and line records with `IBTFlag = 1`

This is the internal replenishment mechanism.

### 5. Fulfill deliveries at stores
For each store-item-day:

- requested quantity comes from the demand matrix
- available quantity comes from current store on-hand after replenishment
- delivered quantity is `min(requested, available)`
- store on-hand decreases by delivered quantity
- delivery rows are written

This is the point where stockouts happen naturally.

### 6. Write sales history
Sales are simplified as:

```text
SalesQuantity = DeliveredQuantity
```

For each delivered item:

- write a sales row
- compute total cost from cost price
- compute total revenue from selling price

So sales are constrained by actual inventory availability.

### 7. Create supplier purchase orders for the DC
On the configured review day, currently Monday:

- compute average DC demand from summed store moving averages
- compute DC target stock
- compute inventory position as on-hand plus on-order
- create supplier POs where inventory position is below target
- schedule future receipt events using supplier lead times
- increase open on-order quantity

This is how upstream replenishment is generated.

### 8. Write final inventory snapshot
At the end of the full run:

- final on-hand inventory for each site-item is written to `Inventory.txt`

The current implementation writes a point-in-time inventory snapshot, not daily inventory history.

## Why the simulator is internally consistent
The logic preserves the key relationships:

- customer order demand comes from the demand matrix
- deliveries cannot exceed store inventory
- sales equal delivered quantity
- store replenishment cannot exceed DC stock
- receipts must come from previously created supplier POs
- final inventory reflects all receipts, shipments, and sales applied in sequence

That is the main value of the simulator: every feed comes from the same internal truth.

## `poc/writers.py`
This module standardizes output writing.

It provides:

- date formatting
- pipe-delimited file writing
- exact feed column lists

The column constants are the feed contracts used by the rest of the project.

That keeps feed shape consistent regardless of where the data was generated.

## How the pieces connect

```text
config.py
  -> master_data.py
  -> calendar_builder.py
  -> demand.py
  -> simulation.py
  -> writers.py
  -> run.py orchestrates the full flow
```

More concretely:

1. `config.py` defines the parameters
2. `master_data.py` creates the static entities and lookups
3. `demand.py` creates requested demand for the full horizon
4. `simulation.py` consumes that demand and applies inventory and replenishment rules
5. `writers.py` writes the final feed files
6. `run.py` controls execution and output organization

## Current Simplifications

This is a pre-MVP, so several simplifications are intentional:

- one DC only
- no transit time from DC to store, same-day arrival
- no returns logic in sales history
- no lost sales feed
- no customer master or loyalty logic
- no capacity constraints
- no supplier priorities
- no multi-currency behavior beyond self-conversion
- final inventory snapshot only
- Excel files are copies of TXT feeds, not independently generated business objects

## Where to change behavior

### Change scenario
Edit `CONFIG["scenario"]` in `poc/config.py`.

### Change size of the demo
Edit:

- `store_count`
- `dc_count`
- `item_count`
- `supplier_count`
- `history_weeks`

### Change demand behavior
Edit:

- `base_demand`
- `seasonal_profiles`
- `weekend_uplift_factor`
- `lumpy_spike_probability`
- `outlier_probability`

### Change replenishment behavior
Edit:

- `store_coverage_days`
- `dc_coverage_days`
- `demand_smoothing_window`
- `dc_review_dow`
- lead time and receipt randomness settings

## Typical Use Case

1. Pick a scenario in `config.py`
2. Run `python run.py`
3. Open the generated TXT feeds for raw integration-style inspection
4. Open the Excel copies for easier business review
5. Compare scenario outputs such as summer vs winter to see category shifts

## Future Extensions

Natural next steps would be:

- daily inventory history feed
- explicit stockout metrics report
- validation suite and data quality report
- configurable scenario library
- store clusters with differentiated demand patterns
- promotion and markdown demand drivers
- customer detail and loyalty feeds
- transfer transit times
- richer supplier behavior
