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
    prompt = f"地雷系で可愛いふわもこ共感！💖 ピンク、白、ぬいぐるみ、癒し！ 画像: {image_url or 'ふわもこ！'} テキスト: {text or 'モフモフ！🧸'} 言語: {lang}"
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=100).to(model.device)
    outputs = model.generate(
        **inputs,
        max_new_tokens=40,
        pad_token_id=tokenizer.pad_token_id,
        do_sample=True,
        temperature=0.7
    )
    reply = tokenizer.decode(outputs[0], skip_special_tokens=True).strip()
    if reply.startswith("地雷系") or reply == prompt:
        reply = None
    return reply or ("え、待って！このふわもこ、みりんてゃの心臓バクバク！🧸💥" if lang == "ja" else random.choice([
        "Wow! So fluffy~ Mirin is obsessed! 💕",
        "Oh my! This cuteness kills me~ Mirin loves it! 🥰",
        "Amazing! Fluffy vibes healing my soul! 🌸"
    ]))

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
    cdn_urls = []
    if did:
        cdn_urls.extend([
            f"https://cdn.bsky.app/img/feed_thumbnail/plain/{did}/{cid}@jpeg",
            f"https://cdn.bsky.app/img/feed_full/plain/{did}/{cid}@jpeg",
        ])
    cdn_urls.extend([
        f"https://cdn.bsky.app/img/feed_thumbnail/plain/{cid}@jpeg",
        f"https://cdn.bsky.app/img/feed_full/plain/{cid}@jpeg",
    ])
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for url in cdn_urls:
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
        common_colors = color_counts.most_common(5)

        fluffy_count = 0
        for color in common_colors:
            r, g, b = color[0][:3]
            if (r > 180 and g > 180 and b > 180) or \
               (r > 180 and g < 180 and b < 180) or \
               (r > 180 and g > 180 and b < 180) or \
               (r > 150 and g > 100 and b < 100) or \
               (r > 150 and g < 100 and b > 100):
                fluffy_count += 1
        if fluffy_count >= 1:
            print("🎉 ふわもこ色検出！")
            return True

        check_text = text.lower()
        keywords = ["ふわふわ", "もこもこ", "かわいい", "fluffy", "cute", "soft", "もふもふ", "愛しい", "癒し", "たまらん", "adorable"]
        if any(keyword in check_text for keyword in keywords):
            print("🎉 キーワード検出！")
            return True

        return False
    except Exception as e:
        print(f"⚠️ 画像解析エラー: {e}")
        return False

def is_quoted_repost(post):
    try:
        actual_post_record = post.post.record if hasattr(post, 'post') else post.record
        if hasattr(actual_post_record, 'embed') and actual_post_record.embed:
            embed = actual_post_record.embed
            if hasattr(embed, 'record') and embed.record:
                return True
            elif hasattr(embed, 'record') and hasattr(embed.record, 'record') and embed.record.record:
                return True
        return False
    except Exception:
        return False

def load_reposted_uris_for_check():
    REPOSTED_FILE = "reposted_uris.txt"
    if os.path.exists(REPOSTED_FILE):
        try:
            with open(REPOSTED_FILE, 'r', encoding='utf-8') as f:
                uris = set(line.strip() for line in f if line.strip())
                return uris
        except Exception:
            return set()
    return set()

def detect_language(client, handle):
    try:
        profile = client.get_profile(actor=handle)
        bio = profile.display_name.lower() + " " + getattr(profile, "description", "").lower()
        if any(kw in bio for kw in ["日本語", "日本", "にほん", "japanese", "jp"]):
            return "ja"
        elif any(kw in bio for kw in ["english", "us", "uk", "en"]):
            return "en"
        return "ja"
    except Exception:
        return "ja"

fuwamoko_uris = {}

def normalize_uri(uri):
    try:
        if not uri.startswith('at://'):
            uri = f"at://{uri.lstrip('/')}"
        parts = uri.split('/')
        if len(parts) >= 5:
            return f"at://{parts[2]}/{parts[3]}/{parts[4]}"
        return uri
    except Exception:
        return uri

def load_fuwamoko_uris():
    global fuwamoko_uris
    fuwamoko_uris.clear()
    lock = filelock.FileLock(FUWAMOKO_LOCK)
    with lock:
        if os.path.exists(FUWAMOKO_FILE):
            try:
                with open(FUWAMOKO_FILE, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            uri, timestamp = line.strip().split("|", 1)
                            fuwamoko_uris[normalize_uri(uri)] = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                print(f"📂 既存ふわもこ履歴を読み込み: {len(fuwamoko_uris)}件")
            except Exception as e:
                print(f"⚠️ 履歴読み込みエラー: {e}")
        else:
            print(f"📂 {FUWAMOKO_FILE} が見つかりません。新規作成します")
            with open(FUWAMOKO_FILE, 'w', encoding='utf-8') as f:
                pass

def save_fuwamoko_uri(uri, indexed_at):
    normalized_uri = normalize_uri(uri)
    lock = filelock.FileLock(FUWAMOKO_LOCK)
    with lock:
        if normalized_uri in fuwamoko_uris and (datetime.now(timezone.utc) - fuwamoko_uris[normalized_uri]).total_seconds() < 24 * 3600:
            return
        try:
            if isinstance(indexed_at, str):
                indexed_at = datetime.fromisoformat(indexed_at.replace("Z", "+00:00"))
            with open(FUWAMOKO_FILE, 'a', encoding='utf-8') as f:
                f.write(f"{normalized_uri}|{indexed_at.isoformat()}\n")
            fuwamoko_uris[normalized_uri] = indexed_at
            print(f"💾 履歴保存: {normalized_uri.split('/')[-1]}")
            load_fuwamoko_uris()
        except Exception as e:
            print(f"⚠️ 履歴保存エラー: {e}")

def load_session_string():
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception:
            return None
    return None

def save_session_string(session_str):
    try:
        with open(SESSION_FILE, 'w', encoding='utf-8') as f:
            f.write(session_str)
    except Exception:
        pass

def process_post(post, client, fuwamoko_uris, reposted_uris):
    try:
        actual_post = post.post if hasattr(post, 'post') else post
        if str(actual_post.uri) in fuwamoko_uris or \
           actual_post.author.handle == HANDLE or \
           is_quoted_repost(post) or \
           str(actual_post.uri).split('/')[-1] in reposted_uris:
            return False

        text = getattr(actual_post.record, "text", "")
        uri = str(actual_post.uri)
        author = actual_post.author.handle
        embed = getattr(actual_post.record, "embed", None)
        indexed_at = actual_post.indexed_at

        image_data_list = []
        if embed and hasattr(embed, 'images') and embed.images:
            image_data_list = embed.images
        elif embed and hasattr(embed, 'record') and hasattr(embed.record, 'embed') and hasattr(embed.record.embed, 'images'):
            image_data_list = embed.record.embed.images
        elif embed and embed.get('$type') == 'app.bsky.embed.recordWithMedia':
            if hasattr(embed, 'media') and hasattr(embed.media, 'images'):
                image_data_list = embed.media.images
        else:
            return False

        if not is_mutual_follow(client, author):
            return False

        if image_data_list:
            image_data = image_data_list[0]
            if process_image(image_data, text, client=client, post=post) and random.random() < 0.5:
                lang = detect_language(client, author)
                reply_text = open_calm_reply("", text, lang=lang)
                reply_ref = models.AppBskyFeedPost.ReplyRef(
                    root=models.ComAtprotoRepoStrongRef.Main(uri=uri, cid=actual_post.cid),
                    parent=models.ComAtprotoRepoStrongRef.Main(uri=uri, cid=actual_post.cid)
                )
                client.send_post(
                    text=reply_text,
                    created_at=datetime.now(timezone.utc).isoformat(),
                    reply=reply_ref
                )
                save_fuwamoko_uri(uri, indexed_at)
                print(f"✅ 返信しました → @{author}")
                return True
        return False
    except Exception as e:
        print(f"⚠️ 投稿処理エラー: {e}")
        return False

def run_once():
    try:
        client = Client()
        session_str = load_session_string()
        if session_str:
            client.login(session_string=session_str)
            print(f"📨 ふわもこBot起動！ セッション再利用")
        else:
            client.login(HANDLE, APP_PASSWORD)
            session_str = client.export_session_string()
            save_session_string(session_str)
            print(f"📨 ふわもこBot起動！ 新規セッション")

        load_fuwamoko_uris()
        reposted_uris = load_reposted_uris_for_check()

        target_post_uri = "at://did:plc:lmntwwwhxvedq3r4retqishb/app.bsky.feed.post/3lr6hwd3a2c2k"
        try:
            thread_response = client.get_post_thread(uri=target_post_uri, depth=2)
            process_post(thread_response.thread, client, fuwamoko_uris, reposted_uris)
        except Exception as e:
            print(f"⚠️ Specific get_post_threadエラー: {e}")

        timeline = client.get_timeline(limit=50)
        feed = timeline.feed
        for post in sorted(feed, key=lambda x: x.post.indexed_at, reverse=True):
            time.sleep(random.uniform(2, 5))
            process_post(post, client, fuwamoko_uris, reposted_uris)

    except Exception as e:
        print(f"⚠️ 実行エラー: {e}")

if __name__ == "__main__":
    load_dotenv()
    run_once()