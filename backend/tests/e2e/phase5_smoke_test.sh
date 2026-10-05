#!/bin/bash
set -uo pipefail
cd /home/claude/quantumfinguard/backend

python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8422 > /tmp/uv_phase5.log 2>&1 &
SERVER_PID=$!

for i in $(seq 1 10); do
  sleep 1
  if curl -s -o /dev/null http://127.0.0.1:8422/api/v1/health; then
    echo "SERVER_UP after ${i}s"
    break
  fi
done

BASE="http://127.0.0.1:8422/api/v1"

curl -s -X POST "$BASE/auth/register" -H "Content-Type: application/json" \
  -d '{"email":"aria@quantumfinguard.dev","full_name":"Aria Kapoor","password":"correct-horse-battery"}' -o /tmp/reg5.json
curl -s -X POST "$BASE/auth/login" -H "Content-Type: application/json" \
  -d '{"email":"aria@quantumfinguard.dev","password":"correct-horse-battery"}' -o /tmp/login5.json
TOKEN=$(python3 -c "import json; print(json.load(open('/tmp/login5.json'))['access_token'])")
echo "TOKEN length: ${#TOKEN}"

echo "### FRAUD SERVICE STATUS (expect ready: true now)"
curl -s "$BASE/fraud/status" -H "Authorization: Bearer $TOKEN"; echo

echo "### GET A REAL INGESTED TRANSACTION"
curl -s "$BASE/transactions?page=1&page_size=1" -H "Authorization: Bearer $TOKEN" -o /tmp/txnlist5.json
TXN_ID=$(python3 -c "import json; print(json.load(open('/tmp/txnlist5.json'))['items'][0]['id'])")
echo "txn id: $TXN_ID"

echo "### SCORE THE TRANSACTION (expect real prediction now, not 501)"
curl -s -w "\nHTTP %{http_code}\n" -X POST "$BASE/fraud/transactions/$TXN_ID/score" -H "Authorization: Bearer $TOKEN"

echo "### RETRIEVE STORED PREDICTIONS FOR THIS TRANSACTION"
curl -s "$BASE/fraud/transactions/$TXN_ID/predictions" -H "Authorization: Bearer $TOKEN"; echo

echo "### MODEL COMPARISON METRICS (real training-run results)"
curl -s "$BASE/fraud/models/metrics" -H "Authorization: Bearer $TOKEN"; echo

echo "### SCORE A MANUALLY-CREATED TRANSACTION (no feature_snapshot -> expect honest 501)"
curl -s -X POST "$BASE/transactions" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"customer_id":"c1","merchant_id":"m1","amount":50,"currency":"USD","timestamp":"2026-08-19T10:00:00Z"}' -o /tmp/manualtxn5.json
MANUAL_ID=$(python3 -c "import json; print(json.load(open('/tmp/manualtxn5.json'))['id'])")
curl -s -w "\nHTTP %{http_code}\n" -X POST "$BASE/fraud/transactions/$MANUAL_ID/score" -H "Authorization: Bearer $TOKEN"

kill $SERVER_PID 2>/dev/null
echo "### DONE"
