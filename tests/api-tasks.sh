#!/usr/bin/env bash
# Pure API tests for task board (GET, POST, PATCH, DELETE).
# Requires: curmux serve (e.g. curmux serve --no-tls --port 8833)
# Usage: BASE_URL=http://localhost:8833 ./tests/api-tasks.sh

set -e
BASE="${BASE_URL:-http://localhost:8833}"
FAIL=0

assert_status() {
  local got=$1 want=$2 msg=$3
  if [ "$got" != "$want" ]; then
    echo "FAIL: $msg (got HTTP $got, want $want)" >&2
    FAIL=1
  fi
}

# 1. Create task
RES=$(curl -s -w '\n%{http_code}' -X POST "$BASE/api/tasks" \
  -H "Content-Type: application/json" \
  -d '{"project":"apitest","title":"PATCH target","description":""}')
CODE=$(echo "$RES" | tail -1)
BODY=$(echo "$RES" | sed '$d')
assert_status "$CODE" "200" "POST /api/tasks"
ID=$(echo "$BODY" | sed -n 's/.*"id": *"\([^"]*\)".*/\1/p')
[ -n "$ID" ] || { echo "FAIL: no id in response" >&2; exit 1; }

# 2. GET todo
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/tasks?status=todo")
assert_status "$CODE" "200" "GET /api/tasks?status=todo"

# 3. PATCH to claimed
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X PATCH "$BASE/api/tasks/$ID" \
  -H "Content-Type: application/json" \
  -d '{"status":"claimed","claimed_by":"test-agent"}')
assert_status "$CODE" "200" "PATCH status=claimed"

# 4. GET (task in claimed)
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/tasks")
assert_status "$CODE" "200" "GET /api/tasks"

# 5. PATCH to done
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X PATCH "$BASE/api/tasks/$ID" \
  -H "Content-Type: application/json" \
  -d '{"status":"done"}')
assert_status "$CODE" "200" "PATCH status=done"

# 6. GET (task in done)
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/tasks")
assert_status "$CODE" "200" "GET /api/tasks after done"

# 7. PATCH back to todo
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X PATCH "$BASE/api/tasks/$ID" \
  -H "Content-Type: application/json" \
  -d '{"status":"todo"}')
assert_status "$CODE" "200" "PATCH status=todo"

# 8. GET (task in todo)
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/tasks")
assert_status "$CODE" "200" "GET /api/tasks after todo"

# 9. Invalid status -> 400
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X PATCH "$BASE/api/tasks/$ID" \
  -H "Content-Type: application/json" \
  -d '{"status":"invalid"}')
assert_status "$CODE" "400" "PATCH invalid status"

# 10. Nonexistent task -> 404
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X PATCH "$BASE/api/tasks/nonexistent-id-12345" \
  -H "Content-Type: application/json" \
  -d '{"status":"done"}')
assert_status "$CODE" "404" "PATCH nonexistent task"

# Cleanup
curl -s -o /dev/null -w "%{http_code}" -X DELETE "$BASE/api/tasks/$ID" >/dev/null || true

if [ $FAIL -eq 0 ]; then
  echo "API tasks: all passed"
else
  exit 1
fi
