import os, json, requests, tensorflow as tf, time
from tensorflow.keras.models import load_model
import numpy as np

# ────────────────────────────────────────────────────────────────────────────────
def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

log("🚀 Starting Comment Listener & Auto-Reply Bot")

# ─── CONFIGURATION ─────────────────────────────────────────────────────────────
PAGE_ID    = os.environ.get("FB_PAGE_ID")
PAGE_TOKEN = os.environ.get("FB_TOKEN")
MODEL_PATH = 'web_model/web_model/intent_model_with_loc.h5'
WORD_IDX   = 'web_model/tokenizer_word_index.json'
INTENTS    = 'web_model/intent_classes.json'
PROV_MAP   = 'web_model/province_index.json'

for var, name in [(PAGE_ID, "FB_PAGE_ID"), (PAGE_TOKEN, "FB_TOKEN")]:
    if not var:
        log(f"❌ Missing env var {name}")
        exit(1)
log("✅ Env vars loaded")

# ─── LOAD MODEL & ARTIFACTS ─────────────────────────────────────────────────────
try:
    model = load_model(MODEL_PATH)
    log("✅ Model loaded")
except Exception as e:
    log(f"❌ Model load failed: {e}")
    exit(1)

try:
    with open(WORD_IDX) as f: word_index = json.load(f)
    with open(INTENTS) as f: intent_labels = json.load(f)
    with open(PROV_MAP) as f: prov_map = json.load(f)
    log("✅ Tokenizer, labels & province map loaded")
except Exception as e:
    log(f"❌ Failed loading JSON files: {e}")
    exit(1)

# ─── TEXT PREPROCESSING ─────────────────────────────────────────────────────────
def preprocess(text):
    log(f"🔧 Preprocessing text: {text}")
    maxLen = 30
    toks = text.lower().replace('[^\\w\\s]', ' ').split()
    toks = [word_index.get(w, word_index.get('<OOV>', 1)) for w in toks][:maxLen]
    toks += [0] * (maxLen - len(toks))

    province = 'UNKNOWN'
    for loc, prov in prov_map.get('__reverse__', {}).items():
        if loc in text.lower():
            province = prov
            break
    provId = prov_map.get(province, prov_map['UNKNOWN'])

    log(f"🗺️ Province detected: {province} (ID: {provId})")
    return np.array([toks]), np.array([[provId]])

def classify(text):
    log(f"🧠 Classifying message: {text}")
    x_seq, x_prv = preprocess(text)
    scores = model.predict([x_seq, x_prv], verbose=0)[0]
    idx = int(np.argmax(scores))
    log(f"📊 Prediction scores: {scores}")
    return intent_labels[idx], scores[idx]

# ─── FETCH YOUR PAGE’S POSTS ────────────────────────────────────────────────────
def get_page_posts():
    log("🌐 Fetching page posts")
    url = f"https://graph.facebook.com/v19.0/{PAGE_ID}/posts"
    resp = requests.get(url, params={
        "access_token": PAGE_TOKEN,
        "fields": "id,created_time"
    })
    if not resp.ok:
        log(f"❌ Failed to fetch posts: {resp.text}")
        return []
    posts = [p['id'] for p in resp.json().get('data', [])]
    log(f"📄 Found {len(posts)} posts")
    return posts

# ─── FETCH COMMENTS FOR A POST ──────────────────────────────────────────────────
def get_comments(post_id):
    log(f"💬 Fetching comments for post {post_id}")
    url = f"https://graph.facebook.com/v19.0/{post_id}/comments"
    resp = requests.get(url, params={
        "access_token": PAGE_TOKEN,
        "fields": "id,message,created_time"
    })
    if not resp.ok:
        log(f"❌ Failed to fetch comments: {resp.text}")
        return []
    return resp.json().get('data', [])

# ─── REPLY TO A COMMENT ─────────────────────────────────────────────────────────
def reply(comment_id, text):
    log(f"✍️ Replying to comment {comment_id}")
    url = f"https://graph.facebook.com/v19.0/{comment_id}/comments"
    resp = requests.post(url, json={
        "access_token": PAGE_TOKEN,
        "message": text
    })
    if resp.ok:
        log(f"✅ Replied to {comment_id}")
    else:
        log(f"⚠️ Reply failed {comment_id}: {resp.text}")

# ─── TRACKING ALREADY-REPLIED COMMENTS ───────────────────────────────────────────
seen = set()

# ─── MAIN LOOP ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log("🔁 Starting main loop")
    posts = get_page_posts()
    log(f"🔍 Monitoring {len(posts)} posts for new comments")

    for post_id in posts:
        comments = get_comments(post_id)
        log(f"📥 Received {len(comments)} comments from post {post_id}")

        for c in comments:
            cid, msg = c['id'], c.get('message', '').strip()
            if not msg:
                log(f"⏭️ Skipping empty message {cid}")
                continue
            if cid in seen:
                log(f"🔁 Already processed {cid}")
                continue

            seen.add(cid)
            intent, conf = classify(msg)
            log(f"💬 Comment {cid[:8]}… intent={intent}, confidence={conf:.2%}")

            if intent.startswith("looking_for_") and conf > 0.6:
                reply_text = (
                    f"Hi! It seems you’re {intent.replace('_', ' ')}. "
                    "Check out XtraSpace App: https://play.google.com/store/apps/details?id=com.xtraspace.app"
                )
                reply(cid, reply_text)
            else:
                log("↩️ No auto-reply for this intent")

    log("🏁 Done checking comments")
