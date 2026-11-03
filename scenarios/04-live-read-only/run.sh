#!/usr/bin/env bash
# Scenario 04 — LIVE, READ-ONLY: the read-only dashboard door and the converger's
# report, against your own goatnet, with your own NetBird token.
#
# Needs: your own goatnet's mesh joined (the read door's name is mesh-only), its
# scope in MCC_SCOPE and its zone in MCC_SITE_ZONE, a NetBird personal access token
# of your own in GOAT_NB_API_TOKEN, curl, and for the last steps the goat CLI. Changes nothing: every request is a read, or a write
# the door refuses (and whose body is invalid, so it could create nothing even
# if it got through).
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/lib/hello-mcc.sh"
mc_preflight || exit 1

SCOPE="${MCC_SCOPE:-}"
SITE_ZONE="${MCC_SITE_ZONE:-}"
if [ -z "$SCOPE" ] || [ -z "$SITE_ZONE" ]; then
  mc_fail "set MCC_SCOPE (your goatnet's scope, e.g. zagros-dev) and MCC_SITE_ZONE (its zone,"
  mc_fail "the part after mgmt-read. in your read door's name), then run this again."
  mc_note "this is the one scenario that needs a goatnet. Scenarios 01, 02, 03 and 05 run offline."
  exit 2
fi
PREFIX="$(printf '%s' "$SCOPE" | tr '[:lower:]' '[:upper:]')"
READ_DOOR="https://mgmt-read.${SITE_ZONE}"
TOKEN="${GOAT_NB_API_TOKEN:-}"
GOAT="${GOAT_BIN:-goat}"

mc_banner "Live, read-only — the dashboard is for looking" \
          "$SCOPE: GET is answered, a write is refused at the door; the converger reports." \
          "against your goatnet ($SCOPE) — reads only"

mc_step "Are you on the $SCOPE mesh?"
mc_cmd "resolve mgmt-read.${SITE_ZONE}"
if "$MC_PY" -c "import socket,sys; socket.getaddrinfo(sys.argv[1], 443)" "mgmt-read.${SITE_ZONE}" 2>/dev/null; then
  mc_ok "the name resolves — you are on a mesh that serves ${SITE_ZONE}"
  ON_MESH=1
else
  mc_fail "mgmt-read.${SITE_ZONE} does not resolve"
  mc_note "the read door's name exists only inside your goatnet's mesh. Connect your NetBird"
  mc_note "client to that goatnet and run this again."
  ON_MESH=0
  MC_FAIL=$((MC_FAIL+1))
fi

mc_step "Without a token, the door asks who you are"
if [ "$ON_MESH" = 1 ]; then
  mc_cmd "curl -s -o /dev/null -w '%{http_code}' ${READ_DOOR}/api/groups"
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "${READ_DOOR}/api/groups")
  echo "$code" | mc_quote
  mc_assert "401 — reading needs an identity" [ "$code" = 401 ]
else
  mc_skip "not on the $SCOPE mesh"
fi

if [ -z "$TOKEN" ]; then
  mc_step "Your token"
  mc_fail "GOAT_NB_API_TOKEN is not set"
  mc_note "create a personal access token for YOUR user in your goatnet's NetBird dashboard"
  mc_note "(your user -> access tokens), then:  export GOAT_NB_API_TOKEN=<token>"
  mc_note "it carries your own role. On a governed goatnet that is auditor for platform and identity admins:"
  mc_note "it can read every peer and group and change nothing."
  mc_note "if your dashboard does not offer you a token, ask a platform admin."
  MC_FAIL=$((MC_FAIL+1))
fi

mc_step "GET on the read door: answered"
if [ "$ON_MESH" = 1 ] && [ -n "$TOKEN" ]; then
  mc_cmd "curl -H 'Authorization: Token \$GOAT_NB_API_TOKEN' ${READ_DOOR}/api/groups"
  code=$(curl -s -o "$MC_RUN/groups.json" -w '%{http_code}' --max-time 15 \
           -H "Authorization: Token ${TOKEN}" "${READ_DOOR}/api/groups")
  echo "$code" | mc_quote
  mc_assert "200 — the read-only door serves reads" [ "$code" = 200 ]
  if [ "$code" = 200 ]; then
    "$MC_PY" - "$MC_RUN/groups.json" "$PREFIX" <<'PY' | mc_quote
import json, sys
g = json.load(open(sys.argv[1]))
prefix = sys.argv[2] + "-"
mine = sorted(x["name"] for x in g if x["name"].startswith(prefix))
print(f"{len(g)} groups; {len(mine)} are {prefix}* (the ones warrant manages on this scope), e.g.")
for n in mine[:6]:
    print("  " + n)
PY
  fi
  rm -f "$MC_RUN/groups.json"
else
  mc_skip "needs the mesh and a token"
fi

mc_step "POST on the read door: refused before it reaches the management server"
if [ "$ON_MESH" = 1 ] && [ -n "$TOKEN" ]; then
  mc_say "The body is deliberately invalid (an empty group name). If this request ever got"
  mc_say "through, the management server would reject it; it cannot create anything."
  mc_cmd "curl -X POST -H 'Authorization: Token \$GOAT_NB_API_TOKEN' -d '{\"name\":\"\"}' ${READ_DOOR}/api/groups"
  code=$(curl -s -o "$MC_RUN/post.out" -w '%{http_code}' --max-time 15 -X POST \
           -H "Authorization: Token ${TOKEN}" -H 'Content-Type: application/json' \
           -d '{"name":""}' "${READ_DOOR}/api/groups")
  { echo "$code"; head -c 200 "$MC_RUN/post.out"; echo; } | mc_quote
  rm -f "$MC_RUN/post.out"
  mc_assert "403 — the everyday dashboard's API door forwards only GET, HEAD and OPTIONS" [ "$code" = 403 ]
  mc_note "this is the door the everyday dashboard (dashboard.<site>) talks to. Even the"
  mc_note "NETBIRD-ADMIN holders are read-only there; they write from the admin address (admin-dashboard.<site>)"
  mc_note "and on a governed goatnet a membership edit made there is put back by the converger."
else
  mc_skip "needs the mesh and a token"
fi

mc_step "Your goat CLI"
if command -v "$GOAT" >/dev/null 2>&1; then
  ver=$("$GOAT" --version 2>/dev/null | awk '{print $2}')
  echo "$GOAT $ver" | mc_quote
  if "$GOAT" warrant apply --help 2>/dev/null | grep -q -- '--membership'; then
    mc_ok "this goat has \`goat warrant apply --membership\`"
    GOAT_OK=1
  else
    mc_fail "goat ${ver:-?} has no \`warrant apply --membership\`. Build a current one from goatcore (crates/goat-cli)"
    GOAT_OK=0; MC_FAIL=$((MC_FAIL+1))
  fi
else
  mc_fail "no goat on PATH. Build it from goatcore (crates/goat-cli), or set GOAT_BIN"
  GOAT_OK=0; MC_FAIL=$((MC_FAIL+1))
fi

# The declaration to report against: your scope directory, if your goatnet's repository is checked out.
REAL=""
if [ -n "${MCC_MEMBERSHIP_DIR:-}" ]; then REAL="$MCC_MEMBERSHIP_DIR"
elif [ -n "${GOAT_REPO:-}" ] && [ -f "$GOAT_REPO/ops/warrant/membership/$SCOPE/_scope.yaml" ]; then
  REAL="$GOAT_REPO/ops/warrant/membership/$SCOPE"
fi
mc_honest "--file takes the scope DIRECTORY. A goat that reads only the retired single file refuses it;"
mc_honest "if goat refuses a directory below, build a current goat and run this again."

report() { # <scope dir> -> runs the converger in report mode through the read door
  GOAT_NB_API_TOKEN="$TOKEN" "$GOAT" warrant apply --membership --scope "$SCOPE" \
    --file "$1" --mode report --mgmt-url "$READ_DOOR"
}

mc_step "The converger's report against the real declaration"
if [ "$ON_MESH" = 1 ] && [ -n "$TOKEN" ] && [ "$GOAT_OK" = 1 ] && [ -n "$REAL" ]; then
  mc_cmd "goat warrant apply --membership --scope $SCOPE --file $REAL --mode report --mgmt-url $READ_DOOR"
  report "$REAL" 2>&1 | mc_quote
  mc_assert "report mode ran and changed nothing (exit 0)" mc_exit 0 report "$REAL"
  mc_note "this is the same computation the timer on the management host runs every five minutes"
  mc_note "in enforce mode as svc-<site>-warrant. 'every peer holds what the declaration says'"
  mc_note "means nobody has hand-edited membership since its last pass."
elif [ -z "$REAL" ]; then
  mc_warn "no real declaration: set GOAT_REPO to your goatnet's repository (or MCC_MEMBERSHIP_DIR to the scope directory)"
  mc_note "without it, the what-if below stands in for this step"
else
  mc_skip "needs the mesh, a token and the goat CLI"
fi

mc_step "A what-if: your own copy of the declaration, with one extra entry"
if [ "$ON_MESH" = 1 ] && [ -n "$TOKEN" ] && [ "$GOAT_OK" = 1 ]; then
  WHATIF="$MC_RUN/whatif/$SCOPE"
  rm -rf "$MC_RUN/whatif"; mkdir -p "$MC_RUN/whatif"
  if [ -n "$REAL" ]; then
    cp -R "$REAL" "$WHATIF"
    sed -i.bak 's/^converge: .*/converge: report/' "$WHATIF/_scope.yaml" && rm -f "$WHATIF/_scope.yaml.bak"
  else
    mkdir -p "$WHATIF"
    printf 'version: 1\nscope: %s\nconverge: report\n' "$SCOPE" > "$WHATIF/_scope.yaml"
    printf 'version: 1\nscope: %s\ngenerated_from: what-if\npeople: {}\n' "$SCOPE" > "$WHATIF/_baseline.generated.yaml"
    mc_note "no real declaration, so the copy starts empty. Peers the real one covers will show drift:"
    mc_note "your copy leaves them out, and the declaration is the whole truth to the converger."
  fi
  WHATIF_EXPIRES="$("$MC_PY" -c 'import datetime as d; print(d.date.today() + d.timedelta(days=60))')"
  printf 'version: 1\nentries:\n  - peer: peer-demo-not-enrolled-laptop\n    grant: [%s-P2P]\n    owner: you\n    reason: what-if from hello-galaxy-mesh-change-control\n    expires: %s\n' "$PREFIX" "$WHATIF_EXPIRES" > "$WHATIF/whatif.yaml"
  mc_cmd "goat warrant apply --membership --scope $SCOPE --file $WHATIF --mode report --mgmt-url $READ_DOOR"
  report "$WHATIF" 2>&1 | mc_quote
  mc_assert "the entry for a peer that does not exist is reported missing-peer" \
    mc_has "missing-peer" report "$WHATIF"
  mc_say "Your copy's _scope.yaml says converge: report. Asking it to enforce is refused before goat"
  mc_say "opens a connection: the declaration is the ceiling, and the CLI can only lower it."
  mc_cmd "goat warrant apply --membership --scope $SCOPE --file $WHATIF --mode enforce"
  GOAT_NB_API_TOKEN="$TOKEN" "$GOAT" warrant apply --membership --scope "$SCOPE" \
    --file "$WHATIF" --mode enforce --mgmt-url "$READ_DOOR" 2>&1 | mc_quote
  mc_assert "enforce on a converge: report file is refused (exit 2)" \
    mc_exit 2 env GOAT_NB_API_TOKEN="$TOKEN" "$GOAT" warrant apply --membership --scope "$SCOPE" \
      --file "$WHATIF" --mode enforce --mgmt-url "$READ_DOOR"
  mc_honest "three things stand between this step and a change: the converge: report ceiling,"
  mc_honest "the read-only door, and your token's own role. Any one is enough."
else
  mc_skip "needs the mesh, a token and the goat CLI"
fi

echo
mc_say "Next: read scenarios/05-the-pull-request/README.md, then bash scenarios/05-the-pull-request/run.sh"
if [ "$MC_SKIP" -gt 0 ]; then
  mc_warn "INCOMPLETE: $MC_SKIP step(s) did not run. Fix what is marked above and run it again."
  mc_summary; exit 2
fi
mc_summary
