#!/usr/bin/env bash
# Deploy ai-xinca.com: build → verify → stage → rsync → CF purge → health → GSC/IndexNow
# Mirrors kfchow deploy.sh conventions (vps-cf-edge-publish skill).
# Usage:
#   bash scripts/deploy.sh "msg"            # full deploy
#   bash scripts/deploy.sh --dry-run        # backup + build + rsync list (no push/purge)
#   bash scripts/deploy.sh --skip-build     # reuse existing dist/
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

VPS="${VPS:-deploy@147.79.18.35}"
WEBROOT="${WEBROOT:-/var/www/help.xinca.com}"
STAMP="$(date +%Y%m%d-%H%M%S)"
DRY=0
SKIP_BUILD=0
MSG="deploy"
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1 ;;
    --skip-build) SKIP_BUILD=1 ;;
    *) MSG="$a" ;;
  esac
done

log() { echo "[deploy $STAMP] $*"; }

# 1/6 — VPS backup (rollback safety)
log "VPS backup ${WEBROOT} → /tmp/ai-xinca-www-backup-${STAMP}.tgz"
ssh -o BatchMode=yes -o ConnectTimeout=20 "$VPS" "sudo tar czf /tmp/ai-xinca-www-backup-${STAMP}.tgz -C ${WEBROOT%/*} ${WEBROOT##*/} && sudo ls -la /tmp/ai-xinca-www-backup-${STAMP}.tgz"
log "Rollback: ssh $VPS \"sudo tar xzf /tmp/ai-xinca-www-backup-${STAMP}.tgz -C ${WEBROOT%/*}\""

# 2/6 — Build
if [[ "$SKIP_BUILD" -eq 0 ]]; then
  log "Building (astro build)"
  npm run build
fi

# 2b/6 — Regenerate llms.txt from fresh build output (dead-link guard;
#        /faq/q/ + /qa/ aliases deduped into /kb/q/). Aborts on failure.
log "Regenerate llms.txt"
node scripts/generate-llms.mjs dist dist/llms.txt

# 3/6 — Verify dist
log "Verify dist"
for f in index.html sitemap-index.xml; do
  [[ -f "dist/$f" ]] || { echo "MISSING dist/$f"; exit 1; }
done
echo "dist HTML count: $(find dist -name '*.html' | wc -l | tr -d ' ')"
echo "dist size: $(du -sh dist | cut -f1)"

# 4/6 — Stage + rsync to VPS (scoped; NO --delete across webroot — hvac/ orphan stays)
RSYNC_EXCLUDES=(--exclude "hvac/")
if [[ "$DRY" -eq 1 ]]; then
  log "DRY-RUN: would rsync dist/ → ${VPS}:${WEBROOT}/ (no push)"
  rsync -avzn "${RSYNC_EXCLUDES[@]}" "dist/" "${VPS}:/tmp/ai-xinca-dry-${STAMP}/" 2>&1 | head -40 || true
  ssh -o BatchMode=yes -o ConnectTimeout=20 "$VPS" "rm -rf /tmp/ai-xinca-dry-${STAMP}" 2>/dev/null || true
else
  log "Stage ai-xinca → ${VPS}:/tmp/ai-xinca-dist-${STAMP}"
  ssh -o BatchMode=yes -o ConnectTimeout=20 "$VPS" "rm -rf /tmp/ai-xinca-dist-${STAMP} && mkdir -p /tmp/ai-xinca-dist-${STAMP}"
  rsync -az --stats "dist/" "${VPS}:/tmp/ai-xinca-dist-${STAMP}/"
  ssh -o BatchMode=yes -o ConnectTimeout=20 "$VPS" "sudo rsync -az --delete ${RSYNC_EXCLUDES[*]} /tmp/ai-xinca-dist-${STAMP}/ ${WEBROOT}/ && sudo chown -R www-data:www-data ${WEBROOT} && sudo rm -rf /tmp/ai-xinca-dist-${STAMP}"
  log "rsync complete → ${WEBROOT}"
fi

# 5/6 — CF purge (files:[] — zone xinca.com)
if [[ "$DRY" -eq 0 ]]; then
  # xinca-scoped token first (Cache Purge on xinca.com), fallback to shared token
  CF_TOKEN="${CF_API_TOKEN_XINCA:-${CF_API_TOKEN:-}}"
  CF_ZONE="${CF_ZONE_XINCA:-a5111dd78fc21ff12d5f48bb982fd8b7}"
  if [[ -n "$CF_TOKEN" ]]; then
    log "CF purge zone ${CF_ZONE:0:8}… files:[]"
    FILES='["https://help.xinca.com/","https://help.xinca.com/kb/","https://help.xinca.com/faq/","https://help.xinca.com/x/","https://help.xinca.com/x/rss.xml","https://help.xinca.com/sitemap-index.xml"]'
    curl -sS -X POST "https://api.cloudflare.com/client/v4/zones/${CF_ZONE}/purge_cache" \
      -H "Authorization: Bearer ${CF_TOKEN}" -H "Content-Type: application/json" \
      --data "{\"files\":${FILES}}" | python3 -c 'import json,sys; d=json.load(sys.stdin); print("purge_success", d.get("success"))'
  else
    log "WARN no CF_API_TOKEN — purge skipped"
  fi
fi

# 6/6 — Health checks (origin-resolved: DNS still points at GitHub Pages until Phase D)
# Retry each URL up to 3x (transient VPS/network blips like 000000 must not fail a deploy;
# 2026-08-13 incident: /kb/ returned 000000 once at 06:01 and marked the whole job red).
if [[ "$DRY" -eq 0 ]]; then
  FAIL=0
  VPS_IP="${VPS_IP:-147.79.18.35}"
  for u in \
    "/" \
    "/kb/" \
    "/faq/" \
    "/qa/" \
    "/x/" \
    "/x/rss.xml" \
    "/sitemap-index.xml" \
    "/a/ai-building-energy-management/"; do
    code="000"
    for attempt in 1 2 3; do
      code=$(curl -skL -o /dev/null -w "%{http_code}" --resolve "help.xinca.com:443:${VPS_IP}" --max-time 20 "https://help.xinca.com${u}" || echo 000)
      [[ "$code" == "200" ]] && break
      [[ $attempt -lt 3 ]] && sleep 8
    done
    echo "HEALTH $code ${u} (origin)"
    [[ "$code" == "200" ]] || FAIL=1
  done
  [[ "$FAIL" -eq 0 ]] || { echo "HEALTH_FAIL"; exit 1; }
  # GA tag present on landing (origin)
  curl -skL --resolve "help.xinca.com:443:${VPS_IP}" --max-time 20 "https://help.xinca.com/" | grep -q "G-MLH9M91H5W" && echo "GA_OK" || { echo "GA_MISSING"; exit 1; }
  log "Health checks OK (origin)"
fi

# GSC + IndexNow pings (always, unless dry-run)
# Use the Hermes venv python (system python3 is 3.9 and breaks google-auth/cryptography)
PY_BIN="${AI_XINCA_PY:-$HOME/.hermes/hermes-agent/venv/bin/python}"
[[ -x "$PY_BIN" ]] || PY_BIN="python3"
if [[ "$DRY" -eq 0 ]]; then
  log "Pinging search engines"
  "$PY_BIN" scripts/submit-sitemap-gsc.py 2>/dev/null || log "gsc ping skipped/failed"
  "$PY_BIN" scripts/submit-indexnow.py 2>/dev/null || log "indexnow ping skipped/failed"
  # Warm-fetch key URLs with AI-crawler UAs (edge cache + AI Crawl Control signals)
  bash "$HOME/.hermes/scripts/ping-ai-bots.sh" help.xinca.com || log "warm-fetch warnings"
fi

log "Done: $MSG (stamp $STAMP)"

# ============================================================
# CHAT API DEPLOYMENT (optional — only if systemd/service file present)
# ============================================================
# Copies Python chat API to VPS, installs deps, and restarts the service.
# The service is expected to be at /etc/systemd/system/chat-api.service on the VPS.
# Skip this block if scripts/chat_api.py does not exist.
if [[ -f "scripts/chat_api.py" && "$DRY" -eq 0 ]]; then
  log "Deploying chat API to VPS"
  # 1. Create remote directory
  ssh -o BatchMode=yes -o ConnectTimeout=20 "$VPS" "sudo mkdir -p /var/www/ai-xinca-chat && sudo chown deploy:deploy /var/www/ai-xinca-chat"

  # 2. Rsync chat_api.py and requirements
  rsync -az --stats "scripts/chat_api.py" "scripts/requirements-chat.txt" "${VPS}:/var/www/ai-xinca-chat/"

  # 3. Install deps and restart service
  ssh -o BatchMode=yes -o ConnectTimeout=20 "$VPS" "
    cd /var/www/ai-xinca-chat
    python3 -m pip install -q -r requirements-chat.txt 2>/dev/null || pip3 install -q -r requirements-chat.txt 2>/dev/null || echo 'pip install skipped'
    if [[ -f /etc/systemd/system/chat-api.service ]]; then
      sudo systemctl daemon-reload
      sudo systemctl restart chat-api || sudo systemctl start chat-api
      systemctl is-active --quiet chat-api && echo 'chat-api: active' || echo 'chat-api: failed'
    else
      echo 'chat-api.service not installed — copy scripts/chat-api.service to /etc/systemd/system/'
    fi
  "

  # 4. Health check on chat API
  sleep 3
  CHAT_HEALTH=$(ssh -o BatchMode=yes -o ConnectTimeout=20 "$VPS" "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/api/health || echo '000'")
  if [[ "$CHAT_HEALTH" == "200" ]]; then
    log "Chat API health OK"
  else
    log "WARN Chat API health check returned: $CHAT_HEALTH"
  fi
fi
