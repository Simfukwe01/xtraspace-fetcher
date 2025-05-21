// functions/index.js
const functions = require('firebase-functions');
const admin     = require('firebase-admin');
const fetch     = require('node-fetch');
const tf        = require('@tensorflow/tfjs-node');
const path      = require('path');

// ─── Load your service account for Admin SDK ───────────────────────────────
const serviceAccount = require('../public/secrets/xtraspace-c175b-firebase-adminsdk-xdcvk-49bef3f7ef.json');
admin.initializeApp({
  credential: admin.credential.cert(serviceAccount),
});
const db = admin.firestore();

// ─── Point at the local emulator when testing ──────────────────────────────
if (process.env.FUNCTIONS_EMULATOR) {
  console.log("▶️ Running in emulator mode, pointing Firestore to localhost:8080");
  db.settings({ host: "localhost:8080", ssl: false });
}

// ─── Facebook Page credentials ─────────────────────────────────────────────
const PAGE_ID           = "579954655210740";
const PAGE_ACCESS_TOKEN = "EAAJwVlkVeLUBO7u6EJnJhwSxFjkTymXJ3UDRZCzHnFJAGhAc9z2luZCoAi19dwzLdmOenqhGZBKeQb1qy95tyKoyEboY39NovIRdAV6IH0ZC5da2gIZAXyZBYUp38EOZB6nksHHZBagvU9F0JkEGxBoU6n8OZAyORk3DCD0M8oDnWASa9w4MHPF13ihp8uW1CiVZBGZAzP1x4Lqxhw9FAZBPUZChk";

// ─── Load your TF-JS model + JSON artifacts on cold start ───────────────────
let model, tokenizer, intentClasses, provIndex;
(async () => {
  console.log("🔄 Loading TF-JS model and artifacts...");
  const modelPath = 'file://' + path.join(__dirname, '../public/web_model/web_model/model.json');
  model = await tf.loadLayersModel(modelPath);
  tokenizer     = require('../public/web_model/web_model/tokenizer_word_index.json');
  intentClasses = require('../public/web_model/web_model/intent_classes.json');
  provIndex     = require('../public/web_model/web_model/province_index.json');
  console.log("✅ Model and artifacts loaded.");
})();

// ─── Preprocess helper ─────────────────────────────────────────────────────
function preprocess(text) {
  // you can also log the raw text here if you like
  const maxLen = 11;
  const toks = text.toLowerCase()
    .replace(/[^\w\s]/g, ' ')
    .split(/\s+/)
    .map(w => tokenizer[w] || tokenizer['<OOV>'])
    .slice(0, maxLen);
  while (toks.length < maxLen) toks.push(0);

  let province = 'UNKNOWN';
  const lower = text.toLowerCase();
  for (const [loc, prov] of Object.entries(provIndex.__reverse__ || {})) {
    if (lower.includes(loc)) { province = prov; break; }
  }
  const provId = provIndex[province] || provIndex['UNKNOWN'];

  return {
    textTensor: tf.tensor2d([toks], [1, maxLen]),
    provTensor: tf.tensor1d([provId], 'int32')
  };
}

// ─── Scheduled scraper ─────────────────────────────────────────────────────
exports.scrapeFacebook = functions.pubsub
  .schedule('every 5 minutes')
  .onRun(async () => {
    console.log("🕜 scrapeFacebook triggered");
    const keywords = ['rent house lusaka','lodge ndola','event space kitwe'];
    for (const kw of keywords) {
      console.log(`🔍 Searching Facebook posts for keyword: "${kw}"`);
      const res  = await fetch(
        `https://graph.facebook.com/v19.0/search?type=post` +
        `&q=${encodeURIComponent(kw)}` +
        `&access_token=${PAGE_ACCESS_TOKEN}`
      );
      const json = await res.json();
      console.log(`  → Found ${json.data?.length || 0} posts`);
      for (const post of json.data || []) {
        console.log(`    · Saving post ID=${post.id}`);
        await db.collection('scraped_posts').doc(post.id).set({
          message:   post.message || '',
          timestamp: admin.firestore.FieldValue.serverTimestamp(),
          replied:   false
        }, { merge: true });
      }
    }
    console.log("✅ scrapeFacebook completed");
  });

// ─── Auto-reply trigger ─────────────────────────────────────────────────────
exports.autoReply = functions.firestore
  .document('scraped_posts/{postId}')
  .onCreate(async (snap) => {
    console.log("✨ autoReply triggered for doc", snap.id);
    const data = snap.data();
    if (!data.message) {
      console.log("  ✖ No message field, skipping");
      return null;
    }
    if (data.replied) {
      console.log("  ✖ Already replied, skipping");
      return null;
    }

    // classify intent
    console.log("  ▶️ Classifying message:", data.message);
    const { textTensor, provTensor } = preprocess(data.message);
    const scores = model.predict({ text_input: textTensor, prov_input: provTensor }).arraySync()[0];
    const best   = scores.indexOf(Math.max(...scores));
    const intent = intentClasses[best];
    console.log(`  → Predicted intent = ${intent} (score ${scores[best].toFixed(3)})`);

    // if they’re looking for something, reply
    if (intent.startsWith('looking_for_')) {
      const reply = `Hi! It seems you’re ${intent.replace(/_/g,' ')}. ` +
                    `Explore XtraSpace here: https://play.google.com/store/apps/details?id=com.xtraspace.app`;
      console.log("  ✉️ Sending reply:", reply);
      await fetch(
        `https://graph.facebook.com/v19.0/${snap.id}/comments`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: reply,
            access_token: PAGE_ACCESS_TOKEN
          })
        }
      );
      console.log("  ✔️ Reply posted");
      // mark as done
      await snap.ref.update({ replied: true });
      console.log("  🔄 Document updated with replied=true");
    } else {
      console.log("  ✖ Intent is not property-seeking, no reply");
    }
    return null;
  });
