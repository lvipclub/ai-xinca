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
WEBROOT="${WEBROOT:-/var/www/ai.xinca.com}"
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
    FILES='["https://ai.xinca.com/","https://ai.xinca.com/kb/","https://ai.xinca.com/faq/","https://ai.xinca.com/sitemap-index.xml"]'
    curl -sS -X POST "https://api.cloudflare.com/client/v4/zones/${CF_ZONE}/purge_cache" \
      -H "Authorization: Bearer ${CF_TOKEN}" -H "Content-Type: application/json" \
      --data "{\"files\":${FILES}}" | python3 -c 'import json,sys; d=json.load(sys.stdin); print("purge_success", d.get("success"))'
  else
    log "WARN no CF_API_TOKEN — purge skipped"
  fi
fi

# 6/6 — Health checks (origin-resolved: DNS still points at GitHub Pages until Phase D)
if [[ "$DRY" -eq 0 ]]; then
  FAIL=0
  VPS_IP="${VPS_IP:-147.79.18.35}"
  for u in \
    "/" \
    "/kb/" \
    "/faq/" \
    "/qa/" \
    "/sitemap-index.xml" \
    "/a/ai-building-energy-management/"; do
    code=$(curl -skL -o /dev/null -w "%{http_code}" --resolve "ai.xinca.com:443:${VPS_IP}" --max-time 20 "https://ai.xinca.com${u}" || echo 000)
    echo "HEALTH $code ${u} (origin)"
    [[ "$code" == "200" ]] || FAIL=1
  done
  [[ "$FAIL" -eq 0 ]] || { echo "HEALTH_FAIL"; exit 1; }
  # GA tag present on landing (origin)
  curl -skL --resolve "ai.xinca.com:443:${VPS_IP}" --max-time 20 "https://ai.xinca.com/" | grep -q "G-MLH9M91H5W" && echo "GA_OK" || { echo "GA_MISSING"; exit 1; }
  log "Health checks OK (origin)"
fi

# GSC + IndexNow pings (always, unless dry-run)
if [[ "$DRY" -eq 0 ]]; then
  log "Pinging search engines"
  python3 scripts/submit-sitemap-gsc.py 2>/dev/null || log "gsc ping skipped/failed"
  python3 scripts/submit-indexnow.py 2>/dev/null || log "indexnow ping skipped/failed"
fi

log "Done: $MSG (stamp $STAMP)"
