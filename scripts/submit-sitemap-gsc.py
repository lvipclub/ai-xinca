#!/usr/bin/env python3
"""
Submit ai.xinca.com sitemap to Google Search Console.
Uses GMC service account (already has access to sc-domain:xinca.com).
Called after every ai-xinca deploy.
"""
import sys
from google.oauth2 import service_account
from googleapiclient.discovery import build

SERVICE_ACCOUNT = '/home/hermerr/.hermes/skills/shopify-gmc-optimizer/credentials/gmc_service_account.json'
SITE_URL = 'sc-domain:xinca.com'
SITEMAP_URL = 'https://ai.xinca.com/sitemap-index.xml'

def main():
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT,
        scopes=['https://www.googleapis.com/auth/webmasters']
    )
    service = build('webmasters', 'v3', credentials=credentials)
    
    try:
        service.sitemaps().submit(siteUrl=SITE_URL, feedpath=SITEMAP_URL).execute()
        print(f"✅ Sitemap submitted to GSC: {SITEMAP_URL}")
    except Exception as e:
        if '409' in str(e):
            print(f"⚠️  Sitemap already submitted (re-submit not needed): {SITEMAP_URL}")
        else:
            print(f"❌ Submission failed: {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == '__main__':
    main()
