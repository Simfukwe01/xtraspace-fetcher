# scripts/dump_posts.py
import json
import requests

# HARD-CODED for testing only!
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

with open("scraped_posts.json", "w", encoding="utf-8") as f:
    json.dump(all_posts, f, indent=2, ensure_ascii=False)

print(f"✅ Dumped {len(all_posts)} posts to scraped_posts.json")
