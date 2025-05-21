# scripts/scrape_and_reply.py
import os, json, requests, tensorflow as tf
from tensorflow.keras.models import load_model
import numpy as np

# Load FB token from GitHub Actions secret
TOKEN   = os.environ['FB_TOKEN']
PAGE_ID = os.environ['PAGE_ID']

# Load your Keras model, tokenizer, labels & province map
model = load_model('web_model/web_model/model.json')  # you may need a .h5 here, adjust accordingly
word_index    = json.load(open('web_model/tokenizer_word_index.json'))
intent_labels = json.load(open('web_model/intent_classes.json'))
prov_map      = json.load(open('web_model/province_index.json'))

# Mirror your JS preprocess (maxLen = 30)
def preprocess(text):
    maxLen = 30
    toks = text.lower().replace('[^\\w\\s]',' ').split()
    toks = [word_index.get(w, word_index['<OOV>']) for w in toks][:maxLen]
    toks += [0] * (maxLen - len(toks))
    # find province id
    province = 'UNKNOWN'
    for loc, prov in prov_map.get('__reverse__', {}).items():
        if loc in text.lower():
            province = prov
            break
    provId = prov_map.get(province, prov_map['UNKNOWN'])
    # build numpy inputs
    return np.array([toks]), np.array([[provId]])

def classify(text):
    x_seq, x_prov = preprocess(text)
    scores = model.predict([x_seq, x_prov])[0]
    idx    = scores.argmax()
    return intent_labels[idx]

def scrape_keyword(kw):
    url = "https://graph.facebook.com/v19.0/search"
    resp = requests.get(url, params={
      "type": "post", "q": kw, "access_token": TOKEN
    }).json()
    for post in resp.get("data", []):
        msg    = post.get("message", "")
        intent = classify(msg)
        if intent.startswith("looking_for_"):
            comment_url = f"https://graph.facebook.com/v19.0/{post['id']}/comments"
            requests.post(comment_url, json={
              "message": f"Hi! It seems you’re {intent.replace('_',' ')}. Download XtraSpace: https://play.google.com/store/apps/details?id=com.xtraspace.app",
              "access_token": TOKEN
            })

if __name__=="__main__":
    for kw in ["rent house lusaka","lodge ndola","event space kitwe"]:
        scrape_keyword(kw)
