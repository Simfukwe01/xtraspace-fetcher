# scripts/dump_posts.py

import json
import requests
import shutil
import os

# Load from env in production; hard-coded here for quick testing
TOKEN   = 'EAAJwVlkVeLUBO7u6EJnJhwSxFjkTymXJ3UDRZCzHnFJAGhAc9z2luZCoAi19dwzLdmOenqhGZBKeQb1qy95tyKoyEboY39NovIRdAV6IH0ZC5da2gIZAXyZBYUp38EOZB6nksHHZBagvU9F0JkEGxBoU6n8OZAyORk3DCD0M8oDnWASa9w4MHPF13ihp8uW1CiVZBGZAzP1x4Lqxhw9FAZBPUZChk'
PAGE_ID = '579954655210740'

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
    data = resp.json().get("data", [])
    for p in data:
        all_posts.append({
            "id":      p.get("id"),
            "message": p.get("message", "")
        })

# 1) Write JSON at repo root
with open("scraped_posts.json", "w", encoding="utf-8") as f:
    json.dump(all_posts, f, indent=2, ensure_ascii=False)

# 2) Copy into docs/ for GitHub Pages
docs_path = os.path.join("docs", "scraped_posts.json")
shutil.copy("scraped_posts.json", docs_path)

print(f"✅ Dumped {len(all_posts)} posts to scraped_posts.json and {docs_path}")
