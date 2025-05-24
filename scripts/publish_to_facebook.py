# scripts/publish_to_facebook.py

import os
import json
import requests
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import tempfile

print("✅ Starting Facebook Publisher Script")

# —————————————————————————————————————————————————————————————
# 📌 CONFIGURATION (via GitHub Secrets or environment)
try:
    FB_PAGE_ID     = os.environ["FB_PAGE_ID"]
    FB_TOKEN       = os.environ["FB_PAGE_TOKEN"]       # <-- must match your workflow
    GCP_CRED_JSON  = os.environ["GCP_SERVICE_ACCOUNT"]
    print("✅ Environment variables loaded successfully")
except KeyError as e:
    print(f"❌ Missing environment variable: {e}")
    print("🔎 Available environment variables:", list(os.environ.keys()))
    raise

# — Save Firebase credentials JSON to a cross-platform temp file
try:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w") as tf:
        tf.write(GCP_CRED_JSON)
        cred_path = tf.name
    print(f"✅ Firebase credentials saved to temporary file: {cred_path}")
except Exception as e:
    print("❌ Error writing Firebase credentials to file:", e)
    raise

# — Initialize Firestore using the temp file
try:
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("✅ Firebase initialized and Firestore client created")
except Exception as e:
    print("❌ Firebase initialization failed:", e)
    raise

# —————————————————————————————————————————————————————————————
def build_caption(doc):
    data = doc.to_dict()
    loc = f"{data['location']['area']}, {data['location']['town']}"
    caption = f"🏠 {data['type']} now available in {loc}!\n"
    if data.get("number_of_bedrooms"):
        caption += f"🛏️ {data['number_of_bedrooms']} bedrooms\n"
    if data.get("price"):
        caption += f"💰 {data['price']} ({data.get('payment_conditions','')})\n"
    phone = data.get("contact", "").replace("+", "").replace(" ", "")
    if phone:
        caption += f"📱 WhatsApp: https://wa.me/{phone}\n"
    caption += "🔗 More on XtraSpace App: https://play.google.com/store/apps/details?id=com.xtraspace.app"
    return caption

def post_to_fb(caption, image_url):
    url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos"
    payload = {
        "url": image_url,
        "caption": caption,
        "access_token": FB_TOKEN
    }
    print(f"📤 Posting to Facebook: {image_url}")
    r = requests.post(url, data=payload)
    r.raise_for_status()
    return r.json()["post_id"]

def publish_collection(col_name):
    print(f"📂 Processing collection: {col_name}")
    col = db.collection(col_name)
    q = col.where("posted", "==", False)
    for doc in q.stream():
        data = doc.to_dict()
        imgs = data.get("images", {}).get("bedroom", []) + data.get("images", {}).get("outside", [])
        if not imgs:
            print(f"⚠️ [{col_name}] No image for {doc.id}, marking posted")
            doc.reference.update({"posted": True})
            continue

        caption = build_caption(doc)
        try:
            post_id = post_to_fb(caption, imgs[0])
            print(f"✅ [{col_name}] Posted {doc.id} → FB Post ID: {post_id}")

            # Pin the post
            pin_url = f"https://graph.facebook.com/v19.0/{post_id}"
            resp = requests.post(pin_url, data={
                "is_pinned": "true",
                "access_token": FB_TOKEN
            })
            if resp.ok:
                print(f"📌 [{col_name}] Pinned post {post_id}")
            else:
                print(f"⚠️ [{col_name}] Failed to pin post {post_id}: {resp.text}")

            # Mark as posted in Firestore
            doc.reference.update({
                "posted": True,
                "fb_posted_at": datetime.utcnow()
            })
            print(f"📝 [{col_name}] Firestore doc updated: {doc.id}")

        except Exception as e:
            print(f"❌ [{col_name}] ERROR on {doc.id}: {e}")

# —————————————————————————————————————————————————————————————
if __name__ == "__main__":
    print("🚀 Starting publishing process")
    for collection in ("bnb", "event_places", "homes", "houses"):
        publish_collection(collection)
    print("🏁 All collections processed")
