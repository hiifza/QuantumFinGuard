# QuantumFinGuard Frontend

React + TypeScript + Vite. Connects to the real FastAPI backend — no
mock/fake data anywhere; every number on screen comes from a live API
call or shows an honest loading/error/unavailable state.

## Setup

```
npm install
npm run dev
```

By default the app points at `http://127.0.0.1:8000` (set in `.env`).
Change `VITE_API_BASE_URL` if your backend runs elsewhere.

## What's built in this pass

Fully built and verified against a live backend instance (see
verification notes in the delivery message — every API call these
pages make was tested against the real running backend):

- Authentication (login/register, JWT + refresh handling, 401 auto-retry)
- Executive Overview — composed from real endpoints only (dataset
  source breakdown, model metrics, blockchain status, security center,
  copilot status, recent transactions), each section independently
  handling its own loading/error/empty state
- Transactions list (paginated, real data)
- Transaction Investigation — the flagship screen: real risk score,
  real SHAP explanation bars, real behavioral deviation, honest
  blockchain "not applicable" state, real integrity verification, and
  an inline copilot Q&A box scoped to the transaction

## Not yet built (nav items marked "soon")

Fraud & Risk (standalone), Behavioral Intelligence (standalone),
Blockchain Explorer (with the 3D wallet graph), full Copilot page,
Security Center, Quantum-Safe Security panel, Audit Trail, Dataset
Status page. The backend endpoints for all of these already exist and
are live-tested (see backend delivery) — this is a frontend sequencing
gap, not a missing capability. Their routes currently render an honest
"not built in this pass" page rather than a broken link or fake content.

## Design notes

Dark/light theme via `[data-theme]` attribute + CSS custom properties,
matching the visual language established in the earlier landing
page/dashboard (deep blue-black/graphite/emerald/amber/coral in dark
mode; warm beige/cream/stone/sage/bronze in light — toggle not yet
wired to every page's inline styles consistently, see known issues).

The Overview page's 3D risk orb (react-three-fiber) is driven by the
real dataset fraud rate from `/fraud/models/metrics`, not decorative
random motion — if that endpoint is unavailable, the orb still renders
at a neutral baseline rather than blocking the page.

## Known gaps / honest limitations

- No visual/screenshot QA was possible in the build environment
  (no reachable browser binary) — verified via TypeScript compilation,
  production build success, and direct replication of every API call
  each page makes against a live backend, but not human-eye visual QA.
  Please sanity-check the actual rendered UI yourself.
- Light theme is implemented at the token level but not every
  component has been checked against it individually.
- No automated test suite yet.
