#!/bin/bash
set -uo pipefail
cd /home/claude/quantumfinguard/backend

python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8421 > /tmp/uv_phase4.log 2>&1 &
SERVER_PID=$!

for i in $(seq 1 10); do
  sleep 1
  if curl -s -o /dev/null http://127.0.0.1:8421/api/v1/health; then
    echo "SERVER_UP after ${i}s"
    break
  fi
done

BASE="http://127.0.0.1:8421/api/v1"

curl -s -X POST "$BASE/auth/register" -H "Content-Type: application/json" \
  -d '{"email":"aria@quantumfinguard.dev","full_name":"Aria Kapoor","password":"correct-horse-battery"}' -o /tmp/register4.json
echo "register: $(cat /tmp/register4.json)"

curl -s -X POST "$BASE/auth/login" -H "Content-Type: application/json" \
  -d '{"email":"aria@quantumfinguard.dev","password":"correct-horse-battery"}' -o /tmp/login4.json
TOKEN=$(python3 -c "import json; print(json.load(open('/tmp/login4.json'))['access_token'])")
echo "TOKEN length: ${#TOKEN}"

echo "### INGESTION STATUS (should show real_data_available: false for all three)"
curl -s "$BASE/data/ingestion-status" -H "Authorization: Bearer $TOKEN"; echo

echo "### TRANSACTION SOURCE BREAKDOWN (should show ieee_cis_synthetic: 5000, is_synthetic: true)"
curl -s "$BASE/data/transactions/source-breakdown" -H "Authorization: Bearer $TOKEN"; echo

echo "### TRANSACTION LIST (real DB rows from ingestion)"
curl -s "$BASE/transactions?page=1&page_size=2" -H "Authorization: Bearer $TOKEN"; echo

echo "### SECURITY INTEGRITY VERIFY (needs senior_analyst - expect 403 for this analyst user)"
curl -s -w "\nHTTP %{http_code}\n" "$BASE/security/integrity/verify" -H "Authorization: Bearer $TOKEN"

kill $SERVER_PID 2>/dev/null
echo "### DONE"
