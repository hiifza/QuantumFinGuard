#!/bin/bash
set -uo pipefail
cd /home/claude/quantumfinguard/backend

python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8424 > /tmp/uv_phase7.log 2>&1 &
SERVER_PID=$!

for i in $(seq 1 20); do
  sleep 1
  if curl -s -o /dev/null http://127.0.0.1:8424/api/v1/health; then
    echo "SERVER_UP after ${i}s"
    break
  fi
done
sleep 1

BASE="http://127.0.0.1:8424/api/v1"

curl -s -X POST "$BASE/auth/register" -H "Content-Type: application/json" \
  -d '{"email":"aria@quantumfinguard.dev","full_name":"Aria Kapoor","password":"correct-horse-battery"}' -o /tmp/reg7.json
curl -s -X POST "$BASE/auth/login" -H "Content-Type: application/json" \
  -d '{"email":"aria@quantumfinguard.dev","password":"correct-horse-battery"}' -o /tmp/login7.json
TOKEN=$(python3 -c "import json; print(json.load(open('/tmp/login7.json'))['access_token'])")
echo "TOKEN length: ${#TOKEN}"

echo "### FIND AN IBM-SOURCED TRANSACTION"
curl -s "$BASE/data/transactions/source-breakdown" -H "Authorization: Bearer $TOKEN"; echo

IBM_TXN=$(python3 -c "
import sqlite3
conn = sqlite3.connect('quantumfinguard.db')
row = conn.execute(\"SELECT id, customer_id FROM transactions WHERE source_dataset LIKE 'ibm_credit%' LIMIT 1\").fetchone()
print(row[0])
")
IBM_CUSTOMER=$(python3 -c "
import sqlite3
conn = sqlite3.connect('quantumfinguard.db')
row = conn.execute(\"SELECT customer_id FROM transactions WHERE id = ?\", ('$IBM_TXN',)).fetchone()
print(row[0])
")
echo "IBM txn: $IBM_TXN customer: $IBM_CUSTOMER"

echo "### STANDALONE BEHAVIORAL CONTEXT ENDPOINT (real result expected)"
curl -s "$BASE/behavioral/customers/$IBM_CUSTOMER/context?transaction_id=$IBM_TXN" -H "Authorization: Bearer $TOKEN"; echo

echo "### FULL INVESTIGATION VIEW ON IBM TRANSACTION (behavioral should now be 'available')"
curl -s "$BASE/investigation/transactions/$IBM_TXN" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

kill $SERVER_PID 2>/dev/null
echo "### DONE"
