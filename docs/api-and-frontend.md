# API and Frontend Architecture

## Backend API

FastAPI, OpenAPI spec auto-generated and served at /api/openapi.json
(interactive docs at /api/docs). 29 endpoints across 9 resource areas:
auth, transactions, fraud, behavioral, blockchain, security, data
status, investigation, copilot. Every non-auth endpoint requires a
valid JWT (see docs/security-and-pqc.md); role-gated endpoints
additionally check RBAC via a require_role() dependency.

## Frontend

React + TypeScript + Vite. frontend/src/api/ is a typed client layer
written by hand against the real OpenAPI contract:

- types.ts -- TypeScript interfaces for every real response shape
- client.ts -- axios instance, JWT injection, automatic refresh-and-
  retry on 401, a normalized ApiError class distinguishing network
  failures from real HTTP error statuses
- endpoints.ts -- one typed function per backend endpoint

### Pages built and verified (4 of 14 planned)

Login/Register, Executive Overview, Transactions list, Transaction
Investigation (the flagship screen -- real risk score, real SHAP bars,
real behavioral deviation, honest blockchain "not applicable" state,
real integrity check, inline copilot Q&A).

Verification method: TypeScript compilation (zero errors), production
build (succeeds), and a Node.js script that logs in against the live
backend and replicates the exact sequence of API calls each page's
code makes, asserting the real responses match what the TypeScript
types and React components expect. Re-run after the real-dataset
integration to confirm nothing broke (see docs/limitations.md for what
this verification does NOT cover -- visual/rendered-UI review).

### Pages not yet built (9 of 14)

See docs/limitations.md for the full list and status.

## Design system

Dark theme: deep blue-black (#0A0E13) / graphite surfaces / muted
emerald, warm amber, and soft coral accents. Light theme: warm beige /
cream / stone / sage / bronze. Typography: Newsreader (serif,
headlines) + Inter (sans, UI) + IBM Plex Mono (data/code). Established
in the Phase 1-2 landing page and dashboard, carried through
consistently into the React app via CSS custom properties toggled by a
data-theme attribute.
