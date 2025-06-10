# 🔽 📦 Pythonの標準ライブラリ
from datetime import datetime, timezone
import os
import json
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

# 🔽 📡 atproto関連
from atproto import Client, models
from atproto_client.models import AppBskyFeedPost
from atproto_client.exceptions import InvokeTimeoutError

# 🔽 🧠 Transformers用設定
MODEL_NAME = "cyberagent/open-calm-1b"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForCausalLM.from_pretrained(MODEL_NAME)

# 環境変数読み込み
load_dotenv()
HANDLE = os.environ.get("HANDLE")
APP_PASSWORD = os.environ.get("APP_PASSWORD")
SESSION_FILE = "session_string.txt"
FUWAMOKO_FILE = "fuwamoko_empathy_uris.txt"
FUWAMOKO_LOCK = "fuwamoko_empathy_uris.lock"

def open_calm_reply(image_url, text="", context="ふわもこ共感", lang="ja"):
    prompt = f"""地雷系で可愛い、ENFPらしいテンション高めのふわもこ共感！💖
テーマ: ふわもこ、ぬいぐるみ、ピンク、白、癒し、モチモチ
画像: {image_url or 'ピンクと白のふわもこ！'}
テキスト: {text or 'モフモフすぎて秒で刺さった！🧸'}
言語: {lang}"""
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=128)
    outputs = model.generate(**inputs, max_length=60, num_return_sequences=1, pad_token_id=tokenizer.eos_token_id)
    reply = tokenizer.decode(outputs[0], skip_special_tokens=True).strip()
    # プロンプトがそのまま返されるのを防ぐ
    if reply.startswith("地雷系") or reply == prompt:
        reply = None
    return reply or ("え、待って！このふわもこ、完全にみりんてゃの心臓直撃なんだけど！🧸💥" if lang == "ja" else random.choice([
        "Wow! So fluffy~ Mirin is totally obsessed! 💕",
        "Oh my! This cuteness is killing me~ Mirin loves it! 🥰",
        "Amazing! These fluffy vibes are healing my soul! 🌸"
    ]))

def is_mutual_follow(client, handle):
    try:
        their_follows = client.app.bsky.graph.get_follows(params={"actor": handle, "limit": 100})
        their_following = {f.handle for f in their_follows.follows}
        my_follows = client.app.bsky.graph.get_follows(params={"actor": os.environ.get("HANDLE"), "limit": 100})
        my_following = {f.handle for f in my_follows.follows}
        return os.environ.get("HANDLE") in their_following and handle in my_following
    except Exception as e:
        print(f"⚠️ 相互フォロー判定エラー: {e}")
        return False

def download_image_from_blob(cid, client, did=None):
    cdn_urls = []
    if did:
        cdn_urls.extend([
            f"https://cdn.bsky.app/img/feed_thumbnail/plain/{did}/{cid}@jpeg",
            f"https://cdn.bsky.app/img/feed_full/plain/{did}/{cid}@jpeg",
            f"https://cdn.bsky.app/img/feed_full/plain/{did}/{cid}",
            f"https://cdn.bsky.app/img/feed/plain/{did}/{cid}@jpeg",
            f"https://cdn.bsky.app/img/feed/plain/{did}/{cid}",
            f"https://cdn.bsky.app/blob/{did}/{cid}",
        ])
    cdn_urls.extend([
        f"https://cdn.bsky.app/img/feed_thumbnail/plain/{cid}@jpeg",
        f"https://cdn.bsky.app/img/feed_full/plain/{cid}@jpeg",
        f"https://cdn.bsky.app/img/feed_full/plain/{cid}",
        f"https://cdn.bsky.app/img/feed/plain/{cid}@jpeg",
        f"https://cdn.bsky.app/img/feed/plain/{cid}",
        f"https://cdn.bsky.app/blob/{cid}",
    ])
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }
    
    for url in cdn_urls:
        print(f"DEBUG: Trying CDN URL: {url}")
        try:
            response = requests.get(url, stream=True, timeout=10, headers=headers)
            response.raise_for_status()
            print("✅ CDN画像取得成功！")
            return Image.open(BytesIO(response.content))
        except requests.exceptions.RequestException as e:
            print(f"⚠️ CDN画像取得失敗: {e}")
    
    print("❌ 全CDNパターンで画像取得失敗")
    
    if client and did:
        try:
            print(f"DEBUG: Fetching blob via com.atproto.repo.getBlob")
            headers = {
                'Authorization': f'Bearer {client.auth.access_token}',
                'Content-Type': 'application/json'
            }
            params = {'did': did, 'cid': cid}
            response = requests.get('https://bsky.social/xrpc/com.atproto.repo.getBlob', headers=headers, params=params, stream=True, timeout=10)
            response.raise_for_status()
            print("✅ Blob API画像取得成功！")
            return Image.open(BytesIO(response.content))
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Blob API画像取得失敗: {e}")
    
    return None

def process_image(image_data, text="", client=None, post=None):
    if not hasattr(image_data, 'image') or not hasattr(image_data.image, 'ref') or not hasattr(image_data.image.ref, 'link'):
        print("⚠️ 画像CIDが見つかりません")
        return False

    cid = image_data.image.ref.link
    try:
        author_did = post.post.author.did if post and hasattr(post, 'post') else None
        img = download_image_from_blob(cid, client, did=author_did)
        if img is None:
            print("⚠️ 画像取得失敗")
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
                print(f"📌 引用リポスト検出: {embed.record.uri.split('/')[-1]}")
                return True
            elif hasattr(embed, 'record') and hasattr(embed.record, 'record') and embed.record.record:
                print(f"📌 引用リポスト検出 (RecordWithMedia): {embed.record.record.uri.split('/')[-1]}")
                return True
        return False
    except Exception as e:
        print(f"⚠️ 引用リポストチェックエラー: {e}")
        return False

def load_reposted_uris_for_check():
    REPOSTED_FILE = "reposted_uris.txt"
    if os.path.exists(REPOSTED_FILE):
        try:
            with open(REPOSTED_FILE, 'r', encoding='utf-8') as f:
                uris = set(line.strip() for line in f if line.strip())
                print(f"✅ 読み込んだ reposted_uris: {len(uris)}件")
                return uris
        except Exception as e:
            print(f"⚠️ reposted_uris読み込みエラー: {e}")
            return set()
    return set()

def detect_language(client, handle):
    try:
        profile = client.app.bsky.actor.get_profile(params={"actor": handle})
        bio = profile.display_name.lower() + " " + getattr(profile, "description", "").lower()
        if any(kw in bio for kw in ["日本語", "日本", "にほん", "japanese", "jp"]):
            return "ja"
        elif any(kw in bio for kw in ["english", "us", "uk", "en"]):
            return "en"
        return "ja"
    except Exception as e:
        print(f"⚠️ 言語判定エラー: {e}")
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
    except Exception as e:
        print(f"⚠️ URI正規化エラー: {e}")
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
                            fuwamoko_uris[normalize_uri(uri)] = datetime.fromisoformat(timestamp)
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
            print(f"⩗ 履歴保存スキップ（24時間以内）: {normalized_uri.split('/')[-1]}")
            return
        try:
            # indexed_atが文字列ならdatetimeに変換
            if isinstance(indexed_at, str):
                indexed_at = datetime.fromisoformat(indexed_at.replace("Z", "+00:00"))
            with open(FUWAMOKO_FILE, 'a', encoding='utf-8') as f:
                f.write(f"{normalized_uri}|{indexed_at.isoformat()}\n")
            fuwamoko_uris[normalized_uri] = indexed_at
            print(f"💾 履歴保存: {normalized_uri.split('/')[-1]}")
            load_fuwamoko_uris()  # 再読み込み
        except Exception as e:
            print(f"⚠️ 履歴保存エラー: {e}")

def load_session_string():
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, 'r', encoding='utf-8') as f:
                session_str = f.read().strip()
                print(f"✅ セッション文字列読み込み")
                return session_str
        except Exception as e:
            print(f"⚠️ セッション文字列読み込みエラー: {e}")
    return None

def save_session_string(session_str):
    try:
        with open(SESSION_FILE, 'w', encoding='utf-8') as f:
            f.write(session_str)
        print(f"💾 セッション文字列保存")
    except Exception as e:
        print(f"⚠️ セッション文字列保存エラー: {e}")

def process_post(post, client, fuwamoko_uris, reposted_uris):
    try:
        actual_post = post.post if hasattr(post, 'post') else post
        print(f"DEBUG: Processing {actual_post.author.handle}'s post (URI: {actual_post.uri.split('/')[-1]})")
        
        if str(actual_post.uri) in fuwamoko_uris or \
           actual_post.author.handle == HANDLE or \
           is_quoted_repost(post) or \
           str(actual_post.uri).split('/')[-1] in reposted_uris:
            print(f"DEBUG: Skipping post {actual_post.uri.split('/')[-1]}")
            return False

        text = getattr(actual_post.record, "text", "")
        uri = str(actual_post.uri)
        author = actual_post.author.handle
        embed = getattr(actual_post.record, "embed", None)
        indexed_at = actual_post.indexed_at

        image_data_list = []
        if embed and hasattr(embed, 'images') and embed.images:
            image_data_list = embed.images
        elif embed and hasattr(embed, 'record') and hasattr(embed.record, 'embed') and hasattr(embed.record.embed, 'images') and embed.record.embed.images:
            image_data_list = embed.record.embed.images
        elif embed and embed.get('$type') == 'app.bsky.embed.recordWithMedia':
            if hasattr(embed, 'media') and hasattr(embed.media, 'images') and embed.media.images:
                image_data_list = embed.media.images
        else:
            return False

        if not is_mutual_follow(client, author):
            print(f"DEBUG: Skipping post from {author}")
            return False

        if image_data_list:
            image_data = image_data_list[0]
            if not getattr(image_data, 'alt', '').strip():
                print("DEBUG: Image alt text is empty")
            
            if process_image(image_data, text, client=client, post=post) and random.random() < 0.5:
                lang = detect_language(client, author)
                reply_text = open_calm_reply("", text, lang=lang)
                print(f"✨ ふわもこ共感成功 → @{author}")
                reply_ref = AppBskyFeedPost.ReplyRef(
                    root={"$type": "com.atproto.repo.strongRef", "uri": uri, "cid": actual_post.cid},
                    parent={"$type": "com.atproto.repo.strongRef", "uri": uri, "cid": actual_post.cid}
                )
                client.app.bsky.feed.post.create(
                    record=AppBskyFeedPost.Record(
                        text=reply_text,
                        created_at=datetime.now(timezone.utc).isoformat(),
                        reply=reply_ref
                    ),
                    repo=client.me.did
                )
                save_fuwamoko_uri(uri, indexed_at)
                print(f"✅ 返信しました → @{author}")
                return True
            else:
                print(f"🚫 ふわもこ要素なし → @{author}")
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
            client.login(login=HANDLE, password=APP_PASSWORD)
            session_str = client.export_session_string()
            save_session_string(session_str)
            print(f"📨 ふわもこBot起動！ 新規セッション")

        load_fuwamoko_uris()  # 開始時に履歴読み込み
        reposted_uris = load_reposted_uris_for_check()

        target_post_uri = "at://did:plc:lmntwwwhxvedq3r4retqishb/app.bsky.feed.post/3lr6hwd3a2c2k"
        try:
            print(f"🔍 Checking specific post {target_post_uri.split('/')[-1]}")
            thread_response = client.app.bsky.feed.get_post_thread(params={"uri": target_post_uri, "depth": 2})
            if process_post(thread_response.thread, client, fuwamoko_uris, reposted_uris):
                print(f"✅ 特定投稿処理成功")
            else:
                print(f"DEBUG: 特定投稿処理スキップ")
        except Exception as e:
            print(f"⚠️ Specific get_post_threadエラー: {e}")

        timeline = client.app.bsky.feed.get_timeline(params={"limit": 50})
        feed = timeline.feed
        for post in sorted(feed, key=lambda x: x.post.indexed_at, reverse=True):
            time.sleep(random.uniform(2, 5))
            process_post(post, client, fuwamoko_uris, reposted_uris)

    except InvokeTimeoutError:
        print("⚠️ APIタイムアウト！")
    except Exception as e:
        print(f"⚠️ 実行エラー: {e}")

if __name__ == "__main__":
    load_dotenv()
    run_once()