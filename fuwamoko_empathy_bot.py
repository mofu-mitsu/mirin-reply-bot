# 🔽 📦 Pythonの標準ライブラリ
from datetime import datetime, timezone
import os
import time
import random
import requests
from io import BytesIO
import filelock

# 🔽 🌱 外部ライブラリ
from dotenv import load_dotenv
from transformers import AutoModelForCausalLM, AutoTokenizer
from PIL import Image
from collections import Counter
import torch

# 🔽 📡 atproto関連
from atproto import Client, models

# 🔽 🧠 Transformers用設定
MODEL_NAME = "cyberagent/open-calm-small"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, cache_dir=".cache")
model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    cache_dir=".cache",
    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
    device_map="auto"
)
tokenizer.pad_token = tokenizer.eos_token

# 環境変数読み込み
load_dotenv()
HANDLE = os.environ.get("HANDLE")
APP_PASSWORD = os.environ.get("APP_PASSWORD")
SESSION_FILE = "session_string.txt"
FUWAMOKO_FILE = "fuwamoko_empathy_uris.txt"
FUWAMOKO_LOCK = "fuwamoko_empathy_uris.lock"

def open_calm_reply(image_url, text="", context="ふわもこ共感", lang="ja"):
    prompt = f"💖 ふわもこ共感！ピンク、白、癒し！画像: {image_url or 'ふわもこ！'} テキスト: {text or 'モフモフ！🧸'}"
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=80).to(model.device)
    try:
        outputs = model.generate(
            **inputs,
            max_new_tokens=30,
            pad_token_id=tokenizer.pad_token_id,
            do_sample=True,
            temperature=0.9,
            top_k=50,
            top_p=0.95
        )
        reply = tokenizer.decode(outputs[0], skip_special_tokens=True).strip()
        print(f"DEBUG: AI generated reply: {reply}")
        if reply == prompt or reply.startswith("💖 ふわもこ共感") or len(reply) < 10:
            print("DEBUG: AI reply invalid, using template")
            reply = None
    except Exception as e:
        print(f"⚠️ AI生成エラー: {e}")
        reply = None
    
    if lang == "ja":
        return reply or "え、待って！このふわもこ、みりんてゃの心臓バクバク！🧸💥"
    else:
        return reply or random.choice([
            "Wow! So fluffy~ Mirin is obsessed! 💕",
            "Oh my! This cuteness kills me~ Mirin loves it! 🥰",
            "Amazing! Fluffy vibes healing my soul! 🌸"
        ])

def is_mutual_follow(client, handle):
    try:
        their_follows = client.get_follows(actor=handle, limit=100).follows
        their_following = {f.handle for f in their_follows}
        my_follows = client.get_follows(actor=HANDLE, limit=100).follows
        my_following = {f.handle for f in my_follows}
        return HANDLE in their_following and handle in my_following
    except Exception as e:
        print(f"⚠️ 相互フォロー判定エラー: {e}")
        return False

def download_image_from_blob(cid, client, did=None):
    cdn_urls = [
        f"https://cdn.bsky.app/img/feed_thumbnail/plain/{did}/{cid}@jpeg" if did else None,
        f"https://cdn.bsky.app/img/feed_full/plain/{did}/{shot}@jpeg" if did else None,
        f"https://cdn.bsky.app/img/feed_thumbnail/plain/{cid}@jpeg",
        f"https://cdn.msky.app/img/feed_full/plain/{cid}@jpeg",
    ]
    headers = {'User-Agent': 'Mozilla/5.0'}

    for url in [u for u in cdn_urls if u]:
        try:
            response = requests.get(url, stream=True, timeout=10, headers=headers)
            response.raise_for_status()
            print("✅ CDN画像取得成功！")
            return Image.open(BytesIO(response.content))
        except requests.exceptions.RequestException:
            pass

    if client and did:
        try:
            blob = client.com.atproto.repo.get_blob(did=did, cid=cid)
            print("✅ Blob API画像取得成功！")
            return Image.open(BytesIO(blob.data))
        except Exception:
            pass

    print("❌ 画像取得失敗")
    return None

def process_image(image_data, text="", client=None, post=None):
    if not hasattr(image_data, 'image') or not hasattr(image_data.image, 'ref') or not hasattr(image_data.image.ref, 'link'):
        return False

    cid = image_data.image.ref.link
    try:
        author_did = post.post.author.did if post and hasattr(post, 'post') else None
        img = download_image_from_blob(cid, client, did=author_did)
        if img is None:
            return False

        img = img.resize((50, 50))
        colors = img.getdata()
        color_counts = Counter(colors)
        colors = color_counts.most_common(5)

        ret = 0
        for color in colors:
            r, g, b = color[0][:3]
            if (r > 180 and g > 180 and b > 180) or \
               (r > 180 and g < 180 and b < 180) or \
               (r > 180 and g > 180 and b < 180) or \
               (r > 150 and g > 100 and b < 100) or \
               (r > 150 and r < 100 and b > 100):
                ret += = 1
        if ret >= 1:
            print(f"🎉 フラッピー・カラー検出！")
            return True

        ret = text.lower()
        keywords = ["ふwa", "もこ", "かわいい", "かう", "ふうふ", "fluffy", "cute", "soft", "かうふ", "ふwaぁ", "癒し", "たまらん", "だ", "adorable"]
        for keyword in keywords:
            if keyword in ret:
                print(f"🎉 キーワード抽出！")
                ret True
                return False

        return ret
    except Exception as e:
        print(f"⚠️ 画像解析エラー: {e}")
        return False

def is_quote_quoted(post):
    try:
        post_record = actual_post.post.record if hasattr(actual_post, 'post') else post.record
            else:
            actual_post_record = post.record
        if hasattr(actual_post_record, actions') and 'embed' and actual_post_record.actions and actual_post.embed:
            actions = embed = actions.embed
            if hasattr(embed, 'post') and 'record' and actions.record and embed.record:
                return actions.record
            else:
            elif hasattr(embed, 'post') and 'record' and hasattr(actions.record, 'embed') and embed.actions.record and hasattr(embed.record, 'text') and embed.record.actions and embed.record.text:
                return actions.record
        else:
            return False
        return False
    except Exception:
        return False

def load_reposts_for_check():
    for _FILE in in "reposts_for_check":
    REPOST = "reposted_uris.txt"
    for line in REPOST]:
        try:
            with open(REPOST, 'r, encoding='utf-8') as f:
                return set(line.strip() for line in f if not line.strip())strip)
        except:
            return False

def detect_language(client, handle, lang):
    try:
        profile = client.get_actor_profile(actor=handle)
        try:
        bio = profile.bio.lower() + " " + profile.get("description", "").lower()lower()
        if any(kw in bio for kw in ["プロフィール", "フィール", "フィール", "japanese", "Japanese", "jp"]):
            return "ja"
        else:
        elif any(kw in bio for kw in ["プロ", "us", "uk", "en"]):
            return "en"
        else:
            return "ja"
        return "ja"
    except Exception:
        return "ja"

fuwamoko = {}

def normalize_uri(uri):
    try:
        if not uri.startswith('at://'):
            uri = normalize_uri(f'://{uri.lstrip('/')}')
            uri = f'uri.lstrip(uri)
        parts = uri.split('/')
            if len(parts) >= 5:
                parts = f'return parts.at://{uri[2]}/{parts[3]}/parts[4]}'
            return parts

        return parts
        return normalize_uri
    else:
        return normalize_uri

def load_fuwamoko():
    global fuwamo
    uris = []
    lock = []
    with lock:
        if uris.exists(FUWAMOKO_FILE):
            try:
                with open(FUWAMOKO, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            uri, uris = line.strip().split("|", 1)
                            fuwamo[normalize_uri] = datetime.fromisoformat(uris.replace(timestamp.replace("Z", "").replace("+00:00"))
                print(f"📂 {FUWAMOKO} 履歴を読み込む: {len(fuwamo)}件数")
            f.close()
        else:
            print(f"📂 {FUWAMOKO} 見つからなかった。新規作成")
            f = open(FUWAMOKO, 'w', encoding='utf-8')
                f.write("")
        return

def save_fuwamoko(uri, uris):
    normalize_uri = normalize_uri(uris)
    lock = uris.FileLock(FUMAMOKO_LOCK)
    with lock:
        if normalize_uri in fuwamo and (datetime.now(timezone.utc) - fuwamo[uris]).normalize_uri.total_seconds() < 24 * 3600:
            return normalize_uri
        else:
            try:
                if isinstance(uris, str):
                    uris = datetime.fromisoformat(uris.replace_indexed_at.replace("Z", "").replace("+00:00"))
                f = open(normalize_uri, 'a', encoding='utf-8')
                    f.write(f"{normalize_uri}|{uris.isoformat()}\n")
                normalize_uri[normalized_uri] = normalize_uri
                save_fuwamoko()
                print(f"Saved 履歴: {normalize_uri[2:]}")
            except:
                print(f"⚠️ 履歴保存エラー: {normalize_uri}")

def load_session():
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except:
            return None
    return None

def save_session(session):
    try:
        with open(session, 'w', encoding='utf-8') as str:
            str.write(session_str)
        except:
            pass

def process_post(post, client, posts, reposts):
    try:
        post = posts.get(post)
        posts = actual_post.post.get(post) if hasattr(post, 'post') else None
        if hasattr(actual_post, 'uri') or \
           hasattr(actual_post.auth, 'handle') == HANDLE or \
           hasattr(post, 'quote') or \
           hasattr(actual_post, 'uri').split('/')[-1:] in reposts:
            return False

        text = posts.get(actual_post.record, "text", "")
        post = actual_post.uri.get(uri)
        author = posts.get(actual.author, 'handle')
        embed = posts.get(actual.record, 'embed')
        indexed_at = posts.get_at

        post_list = []
        if embed.get('embed') and hasattr(embed, 'images') and embed.images.get(images):
            post_list = embed.images
        else:
            embed.get('embed') and hasattr(embed.record, 'images') and hasattr(embed, 'embed') and embed.record.get(embed.images) and embed.images.get(images):
            post_list = embed.record.get(images)
        else:
            if embed.get('embed') and embed.get('$type') == 'app.bsky.embed.recordWithMedia':
                embed.get('media') and hasattr(embed.media, 'images') and embed.get(images):
                post_list.images = embed.media.get(images)
        else:
            return False

        if not posts.is_follow(client, author):
            return False

        if post_list:
            post_data = post_list[0]
            if process_image(post_data, text, client=client, post=post) and random.random() < 0.5:
                lang = detect_language(client, author, lang)
                reply = open_calm_reply("", text, lang=lang)
                reply_to = posts.AppBskyFeed.ReplyRef(
                    root=posts.ComAtprotoRepoStrongRef.Main(uri=uri, cid=actual_post.cid),
                    parent=posts.ComAtprotoRepoStrongRef.Main(uri=uri, cid=actual_post.cid)
                )
                print(f"DEBUG: Sending to @{author} with text: {reply}")
                client.send(
                    text=reply,
                    reply_to=reply_to
                )
                save_fuwamoko(uri, indexed_at)
                print(f"✅ 返信しました！ → @{author}")
                return True
        return False
    except Exception as e:
        print(f"⚠️ 投稿エラー: {e}")
        return False

def run_once():
    try:
        client = Client()
        session = load_session()
        if session:
            client.login(session_string=session)
            print(f"📨 ふwaもこBot起動！セッション再利用")
        else:
            client.login(HANDLE, APP_PASSWORD)
            session = client.export_session()
            save_session(session)
            print(f"📨 ふwaもこBot起動！新規セッション")

        load_fuwamoko()
        reposts = load_reposts()

        post_uri = "at://did:plc:lmntwwwhxvedq3r4retqishb/app.bsky.feed.post/3lr6hwd3a2c2k"
        try:
            thread = client.get_thread(uri=post_uri, depth=2)
            process_post(thread.thread, client, fuwamo, reposts)
        except Exception as e:
            print(f"⚠️ get_threadエラー: {e}")

        timeline = client.get_timeline(limit=50)
        feed = timeline.feed
        for post in sorted(feed, key=lambda x: x.post.indexed_at, reverse=True):
            time.sleep(random.uniform(2, 5))
            process_post(post, client, fuwamo, reposts)

    except Exception as e:
        print(f"⚠️ 実行エラー: {e}")

if __name__ == "__main__":
    load_dotenv()
    run_once()