#!/bin/bash
set -uo pipefail
cd /home/claude/quantumfinguard/backend

python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8423 > /tmp/uv_phase6.log 2>&1 &
SERVER_PID=$!

for i in $(seq 1 10); do
  sleep 1
  if curl -s -o /dev/null http://127.0.0.1:8423/api/v1/health; then
    echo "SERVER_UP after ${i}s"
    break
  fi
done

BASE="http://127.0.0.1:8423/api/v1"

curl -s -X POST "$BASE/auth/register" -H "Content-Type: application/json" \
  -d '{"email":"aria@quantumfinguard.dev","full_name":"Aria Kapoor","password":"correct-horse-battery"}' -o /tmp/reg6.json
curl -s -X POST "$BASE/auth/login" -H "Content-Type: application/json" \
  -d '{"email":"aria@quantumfinguard.dev","password":"correct-horse-battery"}' -o /tmp/login6.json
TOKEN=$(python3 -c "import json; print(json.load(open('/tmp/login6.json'))['access_token'])")
echo "TOKEN length: ${#TOKEN}"

curl -s "$BASE/transactions?page=1&page_size=1" -H "Authorization: Bearer $TOKEN" -o /tmp/txnlist6.json
TXN_ID=$(python3 -c "import json; print(json.load(open('/tmp/txnlist6.json'))['items'][0]['id'])")
echo "txn id: $TXN_ID"

echo "### SCORE WITH SHAP (expect shap_explanation populated now, not null)"
curl -s -X POST "$BASE/fraud/transactions/$TXN_ID/score" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

echo "### FULL INVESTIGATION VIEW"
curl -s "$BASE/investigation/transactions/$TXN_ID" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

kill $SERVER_PID 2>/dev/null
echo "### DONE"
