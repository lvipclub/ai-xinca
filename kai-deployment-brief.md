Kai — Sloemo's Hermes Browser Automation Bundle deployed on your VPS. Read through, then verify.

---

## What's Already Deployed

I SSH'd in and set up three things:

### 1. Skills Bundle (`~/.hermes/skills/hermes-skills-bundle/`)
9 skills from Sloemo's repo (github.com/sloemo01/hermes-skills-bundle):
- **kimi-webbridge** — Control a real Chrome browser via daemon (navigate, click, type, screenshot, evaluate JS)
- **deep-web-research** — Multi-tab research (10+ tabs) via Kimi
- **osint-person-search** — Cross-platform person verification
- **linkedin-automation** — LinkedIn people search
- **job-search-automation** — Job board scraping
- **mcp-server-research** — Find free MCP servers
- **interactive-prompt-analyzer** — Turn vague prompts → structured plans
- **memory-setup** — Guided memory configuration
- **research-automation-bundle** — Meta-skill loading all 6 research tools

### 2. Kimi WebBridge Daemon
- Binary: `~/.kimi-webbridge/bin/kimi-webbridge` (v1.11.3)
- Running on `http://127.0.0.1:10086`
- **Caveat:** Your VPS is headless — no Chrome. Daemon runs but `extension_connected: false`. The daemon is installed in case you ever connect a Chrome instance. For now, the skill knowledge (how to use it) is more useful than the daemon itself.

### 3. Platform Auth Strategy (`~/.hermes/skills/platform-auth-strategy/SKILL.md`)
Unified recovery playbook for Shopify/X/Google auth:
- **Tier 1 (API):** Token recovery paths for all three platforms — check scopes, re-auth, verify
- **Tier 2 (Browser):** Fallback via Chrome session (limited on your headless VPS)
- **Tier 3 (Manual):** Last-resort guided steps for each platform

---

## What You Need to Do

### Verify the deployment
```
# Check skills loaded
ls ~/.hermes/skills/hermes-skills-bundle/*/SKILL.md

# Check Kimi daemon
~/.kimi-webbridge/bin/kimi-webbridge status

# Check auth strategy
head -3 ~/.hermes/skills/platform-auth-strategy/SKILL.md
```

### NVIDIA API key — OPTIONAL
The bundle README recommends an NVIDIA NIM key (nvapi-...). This is for using Nemotron 3 Ultra as your model. If you're happy with your current model (deepseek, etc.), skip this. The skills work with any model. Only add it if you want to try Nemotron specifically.

### Restart your gateway
After new skills are added, restart so Hermes picks them up:
```
systemctl --user restart hermes-gateway
# or however you restart yours
```

### Test a skill
```
"Use kimi-webbridge to research..."
```
The agent should load the skill and attempt to use the daemon. It'll fail at the browser step (no Chrome), but you'll see the skill load and the daemon respond.

---

## Headless VPS Limitations

Your VPS has no desktop, so:
- `kimi-webbridge` daemon runs but can't control a browser
- `chrome_*` tools need a desktop Chrome
- Browser-based auth fallback (Tier 2 in auth strategy) won't work directly

If you ever want full browser automation, you'd need either:
- Xvfb + headless Chrome on the VPS
- Or connect the daemon to a Chrome instance elsewhere

For now, the value is in the **knowledge** — the auth recovery patterns, research methodologies, and OSINT techniques encoded in the skills work regardless of the daemon state.
