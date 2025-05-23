import os
import json
import requests
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import tempfile

# —————————————————————————————————————————————————————————————
# 📌 CONFIGURATION (via GitHub Secrets or environment)
FB_PAGE_ID = os.environ["FB_PAGE_ID"]
FB_TOKEN = os.environ["FB_TOKEN"]
GCP_CRED_JSON = os.environ["GCP_SERVICE_ACCOUNT"]

# — Save Firebase credentials JSON to a cross-platform temp file
with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w") as f:
    f.write(GCP_CRED_JSON)
    temp_path = f.name

# — Initialize Firestore using the temp file
cred = credentials.Certificate(temp_path)
firebase_admin.initialize_app(cred)
db = firestore.client()

# —————————————————————————————————————————————————————————————
def build_caption(doc):
    data = doc.to_dict()
    loc = data["location"]["area"] + ", " + data["location"]["town"]
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
    r = requests.post(url, data=payload)
    r.raise_for_status()
    return r.json()["post_id"]

def publish_collection(col_name):
    col = db.collection(col_name)
    q = col.where("posted", "==", False)
    for doc in q.stream():
        data = doc.to_dict()
        img = (
            data.get("images", {}).get("bedroom", []) +
            data.get("images", {}).get("outside", [])
        )
        if not img:
            print(f"[{col_name}] No image for {doc.id}, skipping")
            doc.reference.update({"posted": True})
            continue
        caption = build_caption(doc)
        try:
            post_id = post_to_fb(caption, img[0])
            print(f"[{col_name}] Posted {doc.id} → FB {post_id}")
            # Try pinning the post
            pin_url = f"https://graph.facebook.com/v19.0/{post_id}"
            requests.post(pin_url, data={
                "is_pinned": "true",
                "access_token": FB_TOKEN
            })
            print(f"[{col_name}] Pinned {post_id}")
            doc.reference.update({
                "posted": True,
                "fb_posted_at": datetime.utcnow()
            })
        except Exception as e:
            print(f"[{col_name}] ERROR on {doc.id}: {e}")

# —————————————————————————————————————————————————————————————
if __name__ == "__main__":
    for c in ("bnb", "event_places", "homes", "houses"):
        publish_collection(c)
