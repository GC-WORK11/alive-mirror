#!/usr/bin/env bash
# smoke_live.sh — read-only smoke of every demo surface on the live NLB.
#
# Asserts HTTP 200 + the key JSON fields each surface must carry, and
# prints a PASS/FAIL table with per-call ms. Run on demo morning after
# tools/warm_task.py (cold plans honestly time out at the 20 s budget).
#
#   ./scripts/smoke_live.sh [BASE]          # default: the live NLB
#   BASE=http://localhost:8000 ./scripts/smoke_live.sh
#
# Exit 0 = every check passed. No writes: only GETs + /v2/plan POSTs
# (plan is compute-only; it never donates/observes/trips).
set -uo pipefail

BASE="${1:-${BASE:-http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com}}"
BASE="${BASE%/}"
LAT="${LAT:-28.6315}"   # Connaught Place — the demo anchor
LON="${LON:-77.2167}"

pass=0; fail=0
rows=()

# check NAME CODE_EXPECTED JQ_EXPR -- curl args...
# jq_expr runs against the response body; "true" on stdout = assert ok.
# For non-JSON surfaces pass "." and match on code only.
check() {
  local name="$1" want_code="$2" jqexpr="$3"; shift 3
  local out code ms body
  out=$(curl -sS -o /tmp/smoke_body.$$ -w '%{http_code} %{time_total}' \
        --max-time 90 "$@" 2>/dev/null) || out="000 0"
  code="${out% *}"; ms="${out##* }"
  ms=$(python3 -c "print(int(float('$ms')*1000))" 2>/dev/null || echo 0)
  body=$(cat /tmp/smoke_body.$$ 2>/dev/null)
  local verdict="PASS" why=""
  if [ "$code" != "$want_code" ]; then
    verdict="FAIL"; why="http $code != $want_code"
  elif [ "$jqexpr" != "." ]; then
    local res
    res=$(printf '%s' "$body" | jq -r "$jqexpr" 2>/dev/null | tail -1)
    if [ "$res" != "true" ]; then verdict="FAIL"; why="assert: $jqexpr"; fi
  fi
  if [ "$verdict" = "PASS" ]; then pass=$((pass+1)); else fail=$((fail+1)); fi
  rows+=("$(printf '%-26s %-4s %7sms %s' "$name" "$verdict" "$ms" "$why")")
  echo "$name $ms" >> /tmp/smoke_times.$$
}

rm -f /tmp/smoke_times.$$
echo "smoke → $BASE  ($(date -u +%H:%M:%SZ))"

check "GET /health"            200 '.ok == true and .engine == "alive_core" and .field_stale == false' "$BASE/health"
check "GET /aqi"               200 '.pm25 != null and (.pm25|type == "number")' "$BASE/aqi?lat=$LAT&lon=$LON"
check "GET /v2/day"            200 '(.hours|length) > 0 and (.decisions|type == "array")' "$BASE/v2/day?lat=$LAT&lon=$LON"
check "GET /v2/reach walk"     200 '.edge_count > 0' "$BASE/v2/reach?lat=$LAT&lon=$LON&mode=walk&budget_ug=25"
check "GET /v2/outlook"        200 '(.days|length) > 0' "$BASE/v2/outlook?lat=$LAT&lon=$LON"
check "GET /v2/city"           200 '.species != null and .field_age_s != null' "$BASE/v2/city"
check "GET /city page"         200 '.' "$BASE/city"
check "GET /admin page"        200 '.' "$BASE/admin"
check "GET /community"         200 '.obs_total != null' "$BASE/community"
check "GET /grid?h=0"          200 '.type == "FeatureCollection" and (.features|length) > 0' "$BASE/grid?h=0"
check "GET /grid?h=12"         200 '.type == "FeatureCollection" and (.features|length) > 0' "$BASE/grid?h=12"
check "GET /v2/search gazetteer" 200 '(.results|length) > 0 and (.results[0].name | test("India"))' "$BASE/v2/search?q=india+gate"
check "GET /reports"           200 '.type == "FeatureCollection"' "$BASE/reports"
check "GET /tiles/health"      200 '.ok == true' "$BASE/tiles/health"

# plan → strip: strip needs a live route_id minted by /v2/plan
plan_body="{\"from\":{\"lat\":$LAT,\"lon\":$LON},\"to\":{\"lat\":28.495,\"lon\":77.089},\"vehicle\":\"car\"}"
out=$(curl -sS -o /tmp/smoke_plan.$$ -w '%{http_code} %{time_total}' --max-time 90 \
      -X POST "$BASE/v2/plan" -H 'content-type: application/json' -d "$plan_body" 2>/dev/null) || out="000 0"
code="${out% *}"; msv="${out##* }"
ms=$(python3 -c "print(int(float('$msv')*1000))" 2>/dev/null || echo 0)
plan_ok=$(jq -r '(.options|length) > 0 and ([.options[].steps_source] | any(. == "endpoints"))' /tmp/smoke_plan.$$ 2>/dev/null | tail -1)
metro=$(jq -r '[.options[].mode] | any(test("metro"))' /tmp/smoke_plan.$$ 2>/dev/null | tail -1)
nopts=$(jq -r '.options|length' /tmp/smoke_plan.$$ 2>/dev/null)
verdict="PASS"; why=""
[ "$code" != "200" ] && { verdict="FAIL"; why="http $code"; }
[ "$plan_ok" != "true" ] && [ "$verdict" = "PASS" ] && { verdict="FAIL"; why="no engine rows (options=$nopts)"; }
[ "$verdict" = "PASS" ] && { pass=$((pass+1)); } || fail=$((fail+1))
rows+=("$(printf '%-26s %-4s %7sms %s' "POST /v2/plan demo-OD" "$verdict" "$ms" "options=$nopts metro_row=$metro $why")")
echo "POST /v2/plan $ms" >> /tmp/smoke_times.$$

rid=$(jq -r '.options[0].route_id // empty' /tmp/smoke_plan.$$ 2>/dev/null)
if [ -n "$rid" ]; then
  check "GET /v2/strip"       200 '.route_id != null and .step_m != null' "$BASE/v2/strip?route_id=$rid"
else
  rows+=("$(printf '%-26s %-4s %7sms %s' "GET /v2/strip" "SKIP" "-" "no route_id from plan")")
fi

printf '%s\n' "${rows[@]}"
echo "------------------------------------------------------------------"
echo "$pass passed, $fail failed"
rm -f /tmp/smoke_body.$$ /tmp/smoke_plan.$$
[ "$fail" -eq 0 ]
