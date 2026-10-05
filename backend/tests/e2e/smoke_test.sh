#!/bin/bash
set -uo pipefail
cd /home/claude/quantumfinguard/backend
rm -f quantumfinguard.db

python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8420 > /tmp/uv.log 2>&1 &
SERVER_PID=$!

for i in $(seq 1 10); do
  sleep 1
  if curl -s -o /dev/null http://127.0.0.1:8420/api/v1/health; then
    echo "SERVER_UP after ${i}s"
    break
  fi
done

BASE="http://127.0.0.1:8420/api/v1"

echo "### HEALTH"
curl -s "$BASE/health"; echo

echo "### REGISTER"
curl -s -X POST "$BASE/auth/register" -H "Content-Type: application/json" \
  -d '{"email":"aria@quantumfinguard.dev","full_name":"Aria Kapoor","password":"correct-horse-battery"}' \
  -o /tmp/register.json -w "HTTP %{http_code}\n"
cat /tmp/register.json; echo

echo "### LOGIN"
curl -s -X POST "$BASE/auth/login" -H "Content-Type: application/json" \
  -d '{"email":"aria@quantumfinguard.dev","password":"correct-horse-battery"}' \
  -o /tmp/login.json -w "HTTP %{http_code}\n"
cat /tmp/login.json; echo

python3 -c "import json; print(json.load(open('/tmp/login.json'))['access_token'])" > /tmp/token.txt
TOKEN=$(cat /tmp/token.txt)
echo "TOKEN acquired, length: ${#TOKEN}"

echo "### ME"
curl -s "$BASE/auth/me" -H "Authorization: Bearer $TOKEN"; echo

echo "### CREATE TRANSACTION 1"
curl -s -X POST "$BASE/transactions" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"customer_id":"cust_001","merchant_id":"merch_777","merchant_category":"electronics","amount":1499.99,"currency":"USD","timestamp":"2026-08-19T10:15:00Z","device_type":"mobile","card_type":"visa","country":"US"}' \
  -o /tmp/txn1.json
cat /tmp/txn1.json; echo
TXN1_ID=$(python3 -c "import json; print(json.load(open('/tmp/txn1.json'))['id'])")

echo "### CREATE TRANSACTION 2 (tests hash chaining continuity)"
curl -s -X POST "$BASE/transactions" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"customer_id":"cust_002","merchant_id":"merch_112","merchant_category":"grocery","amount":42.10,"currency":"USD","timestamp":"2026-08-19T10:20:00Z","country":"US"}' \
  -o /tmp/txn2.json
cat /tmp/txn2.json; echo

echo "### LIST TRANSACTIONS"
curl -s "$BASE/transactions" -H "Authorization: Bearer $TOKEN"; echo

echo "### FRAUD SCORE (expect honest 501 - no model trained)"
curl -s -w "\nHTTP %{http_code}\n" -X POST "$BASE/fraud/transactions/$TXN1_ID/score" -H "Authorization: Bearer $TOKEN"

echo "### BLOCKCHAIN STATUS (expect ready:false - Neo4j not configured)"
curl -s "$BASE/blockchain/status" -H "Authorization: Bearer $TOKEN"; echo

echo "### PQC STATUS (expect real self-test pass)"
curl -s "$BASE/security/pqc/status" -H "Authorization: Bearer $TOKEN"; echo

echo "### INTEGRITY VERIFY (should be 403 - analyst role, needs senior_analyst)"
curl -s -w "\nHTTP %{http_code}\n" "$BASE/security/integrity/verify" -H "Authorization: Bearer $TOKEN"

kill $SERVER_PID 2>/dev/null
echo "### DONE"
