import os
import requests
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

# —————————————————————————————————————————————————————————————
# 📌 CONFIGURATION (via GitHub Secrets)
FB_PAGE_ID    = os.environ["FB_PAGE_ID"]
TOKEN = os.environ.get("FB_TOKEN")
GCP_CRED_JSON = os.environ["GCP_SERVICE_ACCOUNT"]  # the contents of your service-account.json

# — initialize Firestore
cred = credentials.Certificate(GCP_CRED_JSON)
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
    # WhatsApp
    phone = data.get("contact","").replace("+","").replace(" ","")
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
    # Only docs where posted==False (or missing)
    q = col.where("posted", "==", False)
    for doc in q.stream():
        data = doc.to_dict()
        # pick first image
        img = (
            data.get("images",{})
                .get("bedroom",[]) +
            data.get("images",{})
                .get("outside",[])
        )
        if not img:
            print(f"[{col_name}] No image for {doc.id}, skipping")
            doc.reference.update({"posted": True})
            continue
        caption = build_caption(doc)
        try:
            post_id = post_to_fb(caption, img[0])
            print(f"[{col_name}] Posted {doc.id} → FB {post_id}")
            # pin it
            pin_url = f"https://graph.facebook.com/v19.0/{post_id}"
            requests.post(pin_url, data={
                "is_pinned": "true",
                "access_token": FB_TOKEN
            })
            print(f"[{col_name}] Pinned {post_id}")
            # mark as posted
            doc.reference.update({
                "posted": True,
                "fb_posted_at": datetime.utcnow()
            })
        except Exception as e:
            print(f"[{col_name}] ERROR on {doc.id}: {e}")

if __name__ == "__main__":
    for c in ("bnb","event_places","homes","houses"):
        publish_collection(c)
