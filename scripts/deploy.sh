#!/usr/bin/env bash
# Deploy ai-xinca.com: build → gh-pages → commit → GSC sitemap
# Usage: bash scripts/deploy.sh "Deploy message here"
set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

MSG="${1:-deploy}"

echo "=== 1/4: Build ==="
npm run build

echo ""
echo "=== 2/4: Deploy to gh-pages ==="
rm -rf /tmp/gh-pages-deploy && mkdir /tmp/gh-pages-deploy
cp -r dist/* /tmp/gh-pages-deploy/
echo "ai.xinca.com" > /tmp/gh-pages-deploy/CNAME
touch /tmp/gh-pages-deploy/.nojekyll
cd /tmp/gh-pages-deploy
git init
git add -A
git commit -m "$MSG"
git remote add origin git@github.com:lvipclub/ai-xinca.git
git push -f origin HEAD:gh-pages

echo ""
echo "=== 3/4: Commit source to master ==="
cd "$REPO_ROOT"
git add -A
git commit -m "$MSG" || echo "(no changes to commit)"
git push origin master

echo ""
echo "=== 4/4: Ping search engines ==="
python3 scripts/submit-sitemap-gsc.py
python3 scripts/submit-indexnow.py

echo ""
echo "✅ Deploy complete"
