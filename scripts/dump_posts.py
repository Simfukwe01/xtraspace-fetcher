# scripts/dump_posts.py
import os, json, requests

TOKEN = os.environ['FB_TOKEN']
all_posts = []

for kw in ["rent house lusaka","lodge ndola","event space kitwe"]:
    resp = requests.get(
      "https://graph.facebook.com/v19.0/search",
      params={ "type":"post","q":kw,"access_token":TOKEN }
    ).json()
    for p in resp.get("data", []):
        all_posts.append({
          "id": p["id"],
          "message": p.get("message", "")
        })

with open("scraped_posts.json","w", encoding="utf-8") as f:
    json.dump(all_posts, f, indent=2, ensure_ascii=False)
