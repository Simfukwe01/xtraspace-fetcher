# scripts/dump_posts.py
import os
import sys
import json
import requests

def get_env(name):
    val = os.environ.get(name)
    if not val:
        sys.stderr.write(f"\n❌ Missing environment variable: {name}\n")
        sys.exit(1)
    return val

# Read token and page ID from environment
TOKEN   = get_env('FB_TOKEN')
PAGE_ID = get_env('PAGE_ID')

all_posts = []
keywords = ["rent house lusaka", "lodge ndola", "event space kitwe"]

for kw in keywords:
    resp = requests.get(
        "https://graph.facebook.com/v19.0/search",
        params={
            "type": "post",
            "q": kw,
            "access_token": TOKEN,
            "page": PAGE_ID
        }
    )
    for p in resp.json().get("data", []):
        all_posts.append({
            "id": p.get("id"),
            "message": p.get("message", "")
        })

with open("scraped_posts.json", "w", encoding="utf-8") as f:
    json.dump(all_posts, f, indent=2, ensure_ascii=False)
