import os, json, requests, tensorflow as tf
import numpy as np

# Logging utility
def log(message):
    print(f"[LOG] {message}")

log("Script started.")

# Load FB token from GitHub Actions secret
TOKEN   = os.environ.get('FB_TOKEN')
PAGE_ID = os.environ.get('PAGE_ID')

if not TOKEN:
    log("❌ FB_TOKEN is missing from environment.")
    exit(1)
if not PAGE_ID:
    log("❌ PAGE_ID is missing from environment.")
    exit(1)

log("✅ Environment variables loaded.")

# Load your Keras model, tokenizer, labels & province map
try:
    model = tf.keras.models.load_model('web_model/web_model/intent_model_with_loc.h5')
    log("✅ Model loaded successfully.")
except Exception as e:
    log(f"❌ Failed to load model: {e}")
    exit(1)

try:
    word_index    = json.load(open('web_model/tokenizer_word_index.json'))
    intent_labels = json.load(open('web_model/intent_classes.json'))
    prov_map      = json.load(open('web_model/province_index.json'))
    log("✅ Tokenizer, intent labels, and province map loaded.")
except Exception as e:
    log(f"❌ Failed to load supporting files: {e}")
    exit(1)

# Mirror your JS preprocess (maxLen = 30)
def preprocess(text):
    log(f"Preprocessing text: {text}")
    maxLen = 30
    toks = text.lower().replace('[^\\w\\s]', ' ').split()
    toks = [word_index.get(w, word_index.get('<OOV>', 1)) for w in toks][:maxLen]
    toks += [0] * (maxLen - len(toks))
    
    # Find province id
    province = 'UNKNOWN'
    for loc, prov in prov_map.get('__reverse__', {}).items():
        if loc in text.lower():
            province = prov
            break
    provId = prov_map.get(province, prov_map['UNKNOWN'])
    
    log(f"Tokenized sequence: {toks}")
    log(f"Detected province: {province} (ID: {provId})")
    return np.array([toks]), np.array([[provId]])

def classify(text):
    try:
        x_seq, x_prov = preprocess(text)
        scores = model.predict([x_seq, x_prov])[0]
        idx = scores.argmax()
        intent = intent_labels[idx]
        log(f"Predicted intent: {intent} with confidence: {scores[idx]:.4f}")
        return intent
    except Exception as e:
        log(f"❌ Classification error: {e}")
        return "error"

def scrape_keyword(kw):
    log(f"Searching Facebook posts for keyword: '{kw}'")
    url = "https://graph.facebook.com/v19.0/search"
    try:
        resp = requests.get(url, params={
            "type": "post", "q": kw, "access_token": TOKEN
        }).json()
    except Exception as e:
        log(f"❌ Failed to search Facebook posts: {e}")
        return

    posts = resp.get("data", [])
    log(f"✅ Found {len(posts)} posts for keyword: {kw}")

    for post in posts:
        msg = post.get("message", "")
        if not msg:
            log("⚠️ Skipping post without message.")
            continue
        log(f"Post message: {msg}")
        intent = classify(msg)
        if intent.startswith("looking_for_"):
            comment = f"Hi! It seems you’re {intent.replace('_', ' ')}. Download XtraSpace: https://play.google.com/store/apps/details?id=com.xtraspace.app"
            comment_url = f"https://graph.facebook.com/v19.0/{post['id']}/comments"
            try:
                res = requests.post(comment_url, json={
                    "message": comment,
                    "access_token": TOKEN
                })
                log(f"✅ Commented on post {post['id']}: {comment} (Response: {res.status_code})")
            except Exception as e:
                log(f"❌ Failed to comment on post {post['id']}: {e}")
        else:
            log(f"❌ Intent '{intent}' not suitable for reply.")

if __name__ == "__main__":
    keywords = [
        "rent house lusaka", "lodge ndola", "event space kitwe",
        "boarding house zambia", "rooms for rent kabwe", "guest house chingola",
        "accommodation in livingstone", "bnb in chipata"
    ]
    for kw in keywords:
        scrape_keyword(kw)

log("✅ Script finished.")
