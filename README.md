# QuantumFinGuard

AI and Blockchain Framework for Intelligent Financial Risk and Fraud
Analytics. B.Tech Capstone (BT147), IILM University, Greater Noida.

This is real, working software trained and tested against the real
IEEE-CIS, IBM Credit Card Transactions, and Ethereum Fraud Detection
datasets -- not synthetic placeholders. See
docs/implementation-report.md for the honest, itemized status of
what's real, what's tested, and what's genuinely unfinished.

## Quick start

```
backend/   -> see backend/README.md for setup, dataset placement, and
              training commands (Windows PowerShell instructions included)
frontend/  -> see frontend/README.md
docs/      -> architecture, dataset mapping, ML pipeline, security/PQC,
              RAG, testing, and a consolidated known-limitations list
```

Minimum path to a running system:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# place the 4 real dataset CSVs at backend\data\raw\ (see backend/README.md)
python -m scripts.ingest_data
python -m app.ml.train_fraud_model
uvicorn app.main:app --reload --port 8000
```

```powershell
cd frontend
npm install
npm run dev
```

Then register an account at the frontend URL and open the Transaction
Investigation view on any real transaction.

## What's real vs. what's honestly still missing

Read docs/implementation-report.md first -- it's a one-page,
no-fabrication summary of exactly this. Short version: the backend's
fraud model, SHAP explanations, behavioral analytics, blockchain
graph, integrity chain, and PQC are all real and tested against real
data (104 passing tests). The frontend has 4 of 14 planned screens
built and re-verified against the real backend; the remaining 9 route
to an honest "not built yet" page rather than fake content.
