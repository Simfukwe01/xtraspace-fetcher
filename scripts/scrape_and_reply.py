# scripts/scrape_and_reply.py

import os, json, requests, tensorflow as tf
from tensorflow.keras.models import load_model
import numpy as np

def log(msg):
    print(f"[LOG] {msg}")

log("🚀 Starting scraper & reply bot...")

# ─── Environment ───────────────────────────────────────────────────────────────
# 🔥 TEMP: Hardcoded for testing; remove for production!
TOKEN = os.environ.get("FB_TOKEN")
PAGE_ID = "579954655210740"

if not TOKEN or not PAGE_ID:
    log("❌ Missing TOKEN or PAGE_ID—please configure them!")
    exit(1)
log("✅ Environment variables OK.")

# ─── Load model & artifacts ────────────────────────────────────────────────────
try:
    model = load_model('web_model/web_model/intent_model_with_loc.h5')
    log("✅ Model loaded.")
except Exception as e:
    log(f"❌ Model load error: {e}")
    exit(1)

try:
    word_index    = json.load(open('web_model/tokenizer_word_index.json'))
    intent_labels = json.load(open('web_model/intent_classes.json'))
    prov_map      = json.load(open('web_model/province_index.json'))
    log("✅ Tokenizer, labels & province map loaded.")
except Exception as e:
    log(f"❌ Artifact load error: {e}")
    exit(1)

# ─── Preprocessing & classification ─────────────────────────────────────────────
def preprocess(text):
    log(f"Preprocessing: {text}")
    maxLen = 30
    toks = text.lower().replace('[^\\w\\s]', ' ').split()
    toks = [word_index.get(w, word_index.get('<OOV>', 1)) for w in toks][:maxLen]
    toks += [0] * (maxLen - len(toks))

    # province lookup
    province = 'UNKNOWN'
    for loc, prov in prov_map.get('__reverse__', {}).items():
        if loc in text.lower():
            province = prov
            break
    provId = prov_map.get(province, prov_map['UNKNOWN'])

    log(f"  tokens: {toks}")
    log(f"  province: {province} ({provId})")
    return np.array([toks]), np.array([[provId]])

def classify(text):
    x_seq, x_prov = preprocess(text)
    scores = model.predict([x_seq, x_prov])[0]
    idx = int(np.argmax(scores))
    intent = intent_labels[idx]
    log(f"  intent: {intent} ({scores[idx]:.2f})")
    return intent

# ─── Scrape & reply ──────────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": "Mozilla/5.0 (XtraSpaceBot; +https://xtraspace.app)"
}

# broadened list of realistic search phrases
KEYWORDS = [
    "looking for bed space",
    "need a bed space",
    "bedspace in lusaka",
    "house on rent",
    "house for rent",
    "flat for rent",
    "apartment rent",
    "lodge in ndola",
    "bnb in chipata",
    "accommodation in livingstone",
    "event space kitwe",
    "hall for rent",
    "roommate in lusaka"
]

def scrape_keyword(kw):
    log(f"🔍 Keyword: '{kw}'")
    url = "https://graph.facebook.com/v19.0/search"
    params = {"type":"post", "q":kw, "access_token":TOKEN}
    resp = requests.get(url, params=params, headers=HEADERS)

    try:
        data = resp.json()
    except Exception as e:
        log(f"❌ JSON parse error: {e}")
        return

    log(f"  raw response: {json.dumps(data, indent=2)[:200]}…")
    posts = data.get("data", [])
    log(f"  found {len(posts)} posts")

    for post in posts:
        post_id = post.get("id")
        msg = post.get("message","")
        if not msg:
            log(f"  skipping post {post_id} (no message)")
            continue

        log(f"  post {post_id}: {msg[:60]}…")
        intent = classify(msg)
        if intent.startswith("looking_for_"):
            comment = (
                f"Hi! It seems you’re {intent.replace('_',' ')}. "
                "Download XtraSpace: https://play.google.com/store/apps/details?id=com.xtraspace.app"
            )
            comment_url = f"https://graph.facebook.com/v19.0/{post_id}/comments"
            res = requests.post(comment_url, json={
                "message": comment,
                "access_token": TOKEN
            })
            if res.status_code == 200:
                log(f"  ✅ Commented on {post_id}")
            else:
                log(f"  ⚠️ Comment failed ({res.status_code}): {res.text}")

if __name__ == "__main__":
    for kw in KEYWORDS:
        scrape_keyword(kw)
    log("🎉 All keywords processed.")
