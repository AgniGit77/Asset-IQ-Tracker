# AssetIQ

**Predictive rental & fleet intelligence platform — built for the Caterpillar Hackathon**

> We don't just tell you where your equipment is — we tell you where it should be.

---

## The problem

Construction and mining companies rent out fleets of excavators, cranes, bulldozers, and graders. Today, tracking that fleet is mostly manual — spreadsheets, phone calls, and guesswork. That leads to three recurring failures:

- Equipment goes **missing or unaccounted for** — no site, no operator, no visibility
- Equipment sits **under-utilized** at one site while another site needs it
- Rental teams have **no way to predict** what equipment will be needed next, or when a machine is likely to come back late

AssetIQ turns raw telemetry (engine hours, idle hours, fuel, location) into a single control tower: track → analyze → predict → recommend → act.

---

## What it does

| Capability | What it means |
|---|---|
| **Asset Dashboard** | Live status of every rented asset — active, idle, overdue, unassigned — with fleet-wide KPIs |
| **Check-in / Check-out** | QR-simulated handoff flow: checkout → assign & track → log usage → check-in, every transition logged |
| **Usage Analytics** | Engine hours, idle hours, and fuel converted into a 0–100% Utilization Score per asset |
| **Overdue Alerts** | Flags rentals approaching or past their expected return date |
| **Anomaly Detection** | Flags unassigned equipment, abnormally low utilization, excessive idle time, and abnormal fuel burn |
| **Demand Forecasting** | Predicts which equipment types will be needed at which sites, over the next 7/30/90 days |
| **Recommendation Engine** | Matches under-utilized assets to sites with predicted demand and suggests specific reallocations |
| **Asset Timeline** | A five-horizon forward view per asset — Now / Next 2 hrs / Tonight / Tomorrow / Next week |
| **Idle Loss Calculator** | Converts idle hours into a real cost figure, e.g. *"EQX1002 wasted ₹18,400 of productive capacity today"* |
| **AI Photo Inspection** | Employee uploads 5 photos at check-in; AI classifies damage per zone, scores return condition, and auto-files a maintenance ticket if needed |

---

## How it works

Every asset moves through one strict, fully-traceable lifecycle:

```
Checkout → Assign & Track → Log Usage → Check-in → (back to Available)
```

Every transition writes an immutable event to a single ledger table (`asset_events`). Nothing is overwritten — current status, location, and full history are all derived by reading this ledger. That's what makes every asset traceable end to end, and it's the single source of truth that every other module (utilization, anomalies, forecasting, cost, timeline) reads from.

```
Raw telemetry → Track → Analyze utilization → Detect anomalies
  → Predict demand → Recommend action → Manager approves → System updates
```

---

## Architecture

```
Client (operator app + manager dashboard)
        │
        ▼
API layer (FastAPI)
        │
        ▼
Lifecycle service  →  writes every transition as an event
        │
        ▼
PostgreSQL  →  asset_events ledger, usage logs, equipment, sites, rentals
        │
   ┌────┼─────────┬──────────┬───────────┬───────────┐
   ▼    ▼         ▼          ▼           ▼           ▼
Anomaly  Demand  Timeline   Cost/loss   AI inspection
detection forecast engine   calculator  vision service
   │      │        │          │           │
   └──────┴────────┴──────────┴───────────┘
                 ▼
      Recommendation engine
                 ▼
             Dashboard
```

---

## Tech stack

- **Frontend:** React + Vite, Tailwind CSS, Framer Motion, Recharts, Leaflet
- **Backend:** FastAPI (Python)
- **Database:** PostgreSQL
- **ML:** scikit-learn (Isolation Forest for anomalies), XGBoost / LightGBM (demand forecasting)
- **AI vision:** Claude API (vision) for photo-based damage inspection

---

## Data model

| Table | Purpose |
|---|---|
| `equipment` | Asset master — type, current status |
| `sites` | Site master — location, project type |
| `operators` | Operator master |
| `rentals` | Checkout/expected/actual return dates |
| `usage_logs` | Daily engine hours, idle hours, fuel, operating days |
| `asset_events` | The event ledger — one row per lifecycle transition |
| `alerts` | Generated overdue/anomaly alerts |
| `recommendations` | Generated reallocation suggestions |
| `asset_timeline` | Per-asset forward projection across five horizons |
| `cost_config` | Rental rate, operator cost, fuel cost inputs for the loss calculator |
| `inspection_reports` | AI-generated per-zone damage findings and condition scores |

---

## Formulas

**Utilization Score**
```
Utilization % = Engine Hours / (Engine Hours + Idle Hours) × 100
```

**Idle Loss (₹ wasted per asset per day)**
```
Wasted Value = Idle Hours × (Rental Rate/hr + Operator Cost/hr)
             + Idle Fuel Burn × Fuel Cost/litre
```

---

## MVP build order

1. Asset dashboard + KPI cards
2. Check-in / check-out lifecycle + event ledger
3. Usage analytics + utilization scoring
4. Overdue alerts
5. Anomaly detection
6. Demand forecasting
7. Recommendation engine
8. Asset timeline
9. Idle loss calculator
10. AI photo inspection
11. Fleet efficiency score, live map, what-if simulator *(if time allows)*

---

## Demo narrative

The product is designed to tell one five-minute story:

1. **Spot** — dashboard reveals an asset is unassigned and unused
2. **Explain** — drill into it: no site, no operator, zero runtime
3. **Act** — check in or reallocate the asset live
4. **Predict** — forecasting panel shows a site that will need it next
5. **Prove** — fleet efficiency score visibly increases after the recommended action

---

## What we deliberately left out

No blockchain, no physical RFID/IoT hardware, no chatbot without a task, no sprawling multi-page app. The goal is depth on one credible loop — track, predict, recommend — not breadth of disconnected features.

---

## Team

*Add team member names and roles here.*

## License

*Add license here, or state this is a hackathon submission not intended for production use.*
