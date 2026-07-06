#!/usr/bin/env python3
"""
Ping IndexNow (Bing/Yandex/Seznam) after ai-xinca.com deploy.
Submits the sitemap URL so all pages get crawled at once.
"""
import sys, uuid, urllib.request, urllib.parse

KEY = 'e8a7c3f9-2b4d-4a1e-9f6c-0d5b8a3e7f1c'
SITEMAP_URL = 'https://ai.xinca.com/sitemap-index.xml'

ENGINES = [
    ('Bing', 'https://www.bing.com/indexnow'),
    ('Yandex', 'https://yandex.com/indexnow'),
]

def ping(engine_name, engine_url):
    params = urllib.parse.urlencode({'url': SITEMAP_URL, 'key': KEY})
    url = f'{engine_url}?{params}'
    try:
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status in (200, 202):
                print(f'  ✅ {engine_name}: accepted')
            else:
                print(f'  ⚠️  {engine_name}: HTTP {resp.status}')
    except Exception as e:
        print(f'  ⚠️  {engine_name}: {e}')

def main():
    print(f'=== IndexNow: {SITEMAP_URL} ===')
    for name, url in ENGINES:
        ping(name, url)
    print()

if __name__ == '__main__':
    main()
