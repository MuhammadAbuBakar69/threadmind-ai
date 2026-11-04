# apps/web — Next.js dashboard

```bash
npm install
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1 npm run dev
```

## Planned surfaces (Phase 6, weeks 19–22)

| Surface | Contents | Requirements |
|---|---|---|
| Factory overview | Health indicators, open alerts, throughput | FR-049, FR-050 |
| Machine monitoring | Live condition, anomaly history, maintenance timeline | FR-026, FR-029 |
| Inspection | Image viewer with defect boxes/masks, confirm or correct | FR-016, FR-017, FR-019 |
| Investigation | Ranked hypotheses, evidence links, engineer review actions | FR-033 → FR-036 |
| Reports | PDF generation, CSV export, date/machine/batch filters | FR-051 → FR-054 |
| Administration | Factories, lines, machines, users, roles | FR-002 → FR-012 |

## UI commitments

Every displayed score links to its source record and model version. A number an operator cannot
interrogate is a number they will stop trusting, and rightly so.
