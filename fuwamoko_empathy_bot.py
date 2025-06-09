# 🔽 📦 Pythonの標準ライブラリ
from datetime import datetime, timezone
import os
import json
import time
import random
import requests
from io import BytesIO

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

def open_calm_reply(image_url, text="", context="ふわもこ共感", lang="ja"):
    prompt = f"{context}: 画像: {image_url}, テキスト: {text}, 言語: {lang}"
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=128)
    outputs = model.generate(**inputs, max_length=50, num_return_sequences=1)
    reply = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return reply if reply else ("わぁっ♡ ふわもこすぎる〜！みりん、癒されたよ…💕" if lang == "ja" else random.choice([
        "Wow! So fluffy~ Mirin loves it! 💕",
        "Oh my! This is super cute~ Mirin is happy! 🥰",
        "Amazing! Fluffy vibes~ Mirin is healed! 🌸"
    ]))

def is_mutual_follow(client, handle):
    try:
        their_follows = client.app.bsky.graph.get_follows(params={"actor": handle, "limit": 100})
        their_following = [f.handle for f in their_follows.follows]
        my_follows = client.app.bsky.graph.get_follows(params={"actor": os.environ.get("HANDLE"), "limit": 100})
        my_following = [f.handle for f in my_follows.follows]
        return os.environ.get("HANDLE") in their_following and handle in my_following
    except Exception as e:
        print(f"⚠️ 相互フォロー判定エラー: {e}")
        return False

def get_blob_image_url(cid):
    return f"https://cdn.bsky.app/img/feed_full/plain/{cid}@jpeg"

def download_image_from_blob(cid, client, repo=None):
    cdn_urls = [
        f"https://cdn.bsky.app/img/feed_full/plain/{cid}@jpeg",
        f"https://cdn.bsky.app/img/feed_full/plain/{cid}",
        f"https://cdn.bsky.app/img/feed/plain/{cid}@jpeg",
        f"https://cdn.bsky.app/img/feed/plain/{cid}",
        f"https://cdn.bsky.app/blob/{cid}",
    ]
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
            print(f"⚠️ CDN画像取得失敗 ({url}): {e}")
        except Exception as e:
            print(f"⚠️ CDN画像取得失敗 (予期せぬエラー - {url}): {e}")
    
    print("❌ 全CDNパターンで画像取得失敗")
    return None

def process_image(image_data, text="", client=None, post=None):
    if not hasattr(image_data, 'image') or not hasattr(image_data.image, 'ref') or not hasattr(image_data.image.ref, 'link'):
        print("⚠️ 画像CIDが見つかりません")
        return False

    cid = image_data.image.ref.link
    print(f"DEBUG: CID={cid}")

    try:
        img = download_image_from_blob(cid, client)
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
            if (r > 200 and g > 200 and b > 200) or (r > 200 and g < 150 and b < 150):
                fluffy_count += 1
        if fluffy_count >= 2:
            print("🎉 ふわもこ色検出！")
            return True

        check_text = text.lower()
        keywords = ["ふわふわ", "もこもこ", "かわいい", "fluffy", "cute", "soft"]
        if any(keyword in check_text for keyword in keywords):
            print("🎉 キーワード検出！")
            return True

        return False
    except Exception as e:
        print(f"🔍 DEBUG: 画像解析エラー: {e}")
        return False

def is_quoted_repost(post):
    try:
        if hasattr(post.post.record, 'embed') and post.post.record.embed:
            embed = post.post.record.embed
            if hasattr(embed, 'record'):
                print(f"📌 引用リポスト検出: URI={embed.record.uri}")
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
                print(f"✅ 読み込んだ reposted_uris（チェック用）: {len(uris)}件")
                return uris
        except Exception as e:
            print(f"⚠️ reposted_uris読み込みエラー: {e}")
            return set()
    return set()

def detect_language(client, handle):
    try:
        profile = client.app.bsky.actor.get_profile(params={"actor": handle})
        bio = profile.display_name.lower() + " " + getattr(profile, "description", "").lower()
        if any(kw in bio for kw in ["日本語", "日本", "にほん", "japanese"]):
            return "ja"
        elif any(kw in bio for kw in ["english", "us", "uk"]):
            return "en"
        return "ja"
    except Exception as e:
        print(f"⚠️ 言語判定エラー: {e}")
        return "ja"

FUWAMOKO_FILE = "fuwamoko_empathy_uris.txt"
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
    if os.path.exists(FUWAMOKO_FILE):
        try:
            with open(FUWAMOKO_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        uri, timestamp = line.strip().split("|", 1)
                        fuwamoko_uris[normalize_uri(uri)] = datetime.fromisoformat(timestamp)
            print(f"📂 既存ふわもこ履歴を読み込み: {len(fuwamoko_uris)}件")
            if fuwamoko_uris:
                print(f"📜 履歴サンプル: {list(fuwamoko_uris.keys())[:5]}")
        except Exception as e:
            print(f"⚠️ 履歴読み込みエラー: {e}")
    else:
        print(f"📂 {FUWAMOKO_FILE} が見つかりません。新規作成します")
        with open(FUWAMOKO_FILE, 'w', encoding='utf-8') as f:
            pass

def save_fuwamoko_uri(uri):
    normalized_uri = normalize_uri(uri)
    if normalized_uri in fuwamoko_uris and (datetime.now(timezone.utc) - fuwamoko_uris[normalized_uri]).days < 1:
        print(f"⩗ 履歴保存スキップ（1日1回）: {normalized_uri}")
        return
    try:
        with open(FUWAMOKO_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{normalized_uri}|{datetime.now(timezone.utc).isoformat()}\n")
        fuwamoko_uris[normalized_uri] = datetime.now(timezone.utc)
        print(f"💾 履歴保存: uri={normalized_uri}")
    except Exception as e:
        print(f"⚠️ 履歴保存エラー: {e}")

def load_session_string():
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, 'r', encoding='utf-8') as f:
                session_str = f.read().strip()
                print(f"✅ セッション文字列読み込み: {session_str[:10]}...")
                return session_str
        except Exception as e:
            print(f"⚠️ セッション文字列読み込みエラー: {e}")
    return None

def save_session_string(session_str):
    try:
        with open(SESSION_FILE, 'w', encoding='utf-8') as f:
            f.write(session_str)
        print(f"💾 セッション文字列保存: {session_str[:10]}...")
    except Exception as e:
        print(f"⚠️ セッション文字列保存エラー: {e}")

def run_once():
    try:
        client = Client()
        session_str = load_session_string()
        if session_str:
            client.login(session_string=session_str)
            print(f"📨💖 ふわもこ共感Bot起動！ セッション再利用: {session_str[:10]}...")
        else:
            client.login(login=HANDLE, password=APP_PASSWORD)
            session_str = client.export_session_string()
            save_session_string(session_str)
            print(f"📨💖 ふわもこ共感Bot起動！ 新規セッション: {session_str[:10]}...")

        # 特定投稿を直接取得
        try:
            thread = client.app.bsky.feed.get_post_thread(params={"uri": "at://mofumitsukoubou.bsky.social/app.bsky.feed.post/3lr6hwd3a2c2k", "depth": 2})
            thread_dict = {
                "uri": thread.thread.uri,
                "post": {
                    "author": thread.thread.post.author.handle,
                    "did": thread.thread.post.author.did,
                    "text": getattr(thread.thread.post.record, "text", ""),
                    "embed": getattr(thread.thread.post.record, "embed", None).__dict__ if getattr(thread.thread.post.record, "embed", None) else None
                }
            }
            print(f"🔍 DEBUG: Specific Thread JSON={json.dumps(thread_dict, default=str, ensure_ascii=False, indent=2)}")
        except Exception as e:
            print(f"⚠️ Specific get_post_threadエラー: {e}")

        timeline = client.app.bsky.feed.get_timeline(params={"limit": 20})
        feed = timeline.feed

        load_fuwamoko_uris()
        reposted_uris = load_reposted_uris_for_check()

        for post in sorted(feed, key=lambda x: x.post.indexed_at, reverse=True)[:1]:
            print(f"DEBUG: Post indexed_at={post.post.indexed_at}")
            print(f"DEBUG: Post author={post.post.author.handle}, URI={post.post.uri}")
            post_dict = {
                "uri": post.post.uri,
                "cid": post.post.cid,
                "author": post.post.author.handle,
                "did": post.post.author.did,
                "text": getattr(post.post.record, "text", ""),
                "embed": getattr(post.post.record, "embed", None).__dict__ if getattr(post.post.record, "embed", None) else None
            }
            print(f"🔍 DEBUG: Post JSON={json.dumps(post_dict, default=str, ensure_ascii=False, indent=2)}")

            try:
                thread = client.app.bsky.feed.get_post_thread(params={"uri": post.post.uri, "depth": 2})
                thread_dict = {
                    "uri": thread.thread.uri,
                    "post": {
                        "author": thread.thread.post.author.handle,
                        "did": thread.thread.post.author.did,
                        "text": getattr(thread.thread.post.record, "text", ""),
                        "embed": getattr(thread.thread.post.record, "embed", None).__dict__ if getattr(thread.thread.post.record, "embed", None) else None
                    }
                }
                print(f"🔍 DEBUG: Thread JSON={json.dumps(thread_dict, default=str, ensure_ascii=False, indent=2)}")
            except Exception as e:
                print(f"⚠️ get_post_threadエラー: {e}")

            time.sleep(random.uniform(5, 10))
            text = getattr(post.post.record, "text", "")
            uri = str(post.post.uri)
            post_id = uri.split('/')[-1]
            author = post.post.author.handle
            embed = getattr(post.post.record, "embed", None)

            image_data_list = []
            if embed and hasattr(embed, 'images') and embed.images:
                print("🔍 DEBUG: Found direct embedded images")
                image_data_list = embed.images
                print(f"🔍 DEBUG: Direct images={[{k: getattr(img, k) for k in ['alt', 'image', 'aspect_ratio']} for img in image_data_list]}")
            elif embed and hasattr(embed, 'record') and hasattr(embed.record, 'embed') and hasattr(embed.record.embed, 'images') and embed.record.embed.images:
                print("🔍 DEBUG: Found embedded images in quoted post")
                image_data_list = embed.record.embed.images
                print(f"🔍 DEBUG: Quoted post author={embed.record.author.handle}, DID={embed.record.author.did}")
                print(f"🔍 DEBUG: Quoted images={[{k: getattr(img, k) for k in ['alt', 'image', 'aspect_ratio']} for img in image_data_list]}")
            elif embed and embed.get('$type') == 'app.bsky.embed.recordWithMedia':
                print("🔍 DEBUG: Found recordWithMedia embed")
                if hasattr(embed, 'media') and hasattr(embed.media, 'images') and embed.media.images:
                    image_data_list = embed.media.images
                    print(f"🔍 DEBUG: RecordWithMedia images={[{k: getattr(img, k) for k in ['alt', 'image', 'aspect_ratio']} for img in image_data_list]}")
            else:
                print("🔍 DEBUG: No images found in post")
                continue

            if uri in fuwamoko_uris or author == HANDLE or is_quoted_repost(post) or post_id in reposted_uris:
                continue

            if image_data_list and is_mutual_follow(client, author):
                image_data = image_data_list[0]
                print(f"🔍 DEBUG: image_data={image_data.__dict__}")
                print(f"🔍 DEBUG: image_data keys={list(image_data.__dict__.keys())}")
                if process_image(image_data, text, client=client, post=post) and random.random() < 0.5:
                    lang = detect_language(client, author)
                    reply_text = open_calm_reply("", text, lang=lang)
                    print(f"✨ ふわもこ共感成功 → @{author}: {text} (言語: {lang})")

                    reply_ref = AppBskyFeedPost.ReplyRef(
                        root={"$type": "com.atproto.repo.strongRef", "uri": uri, "cid": post.post.cid},
                        parent={"$type": "com.atproto.repo.strongRef", "uri": uri, "cid": post.post.cid}
                    )

                    client.app.bsky.feed.post.create(
                        record=AppBskyFeedPost.Record(
                            text=reply_text,
                            created_at=datetime.now(timezone.utc).isoformat(),
                            reply=reply_ref
                        ),
                        repo=client.me.did
                    )
                    save_fuwamoko_uri(uri)
                    print(f"✅ 返信しました → @{author}")
                else:
                    print(f"🚫 ふわもこ要素なしまたは確率外 → @{author}")

    except InvokeTimeoutError:
        print("⚠️ APIタイムアウト！")
    except Exception as e:
        print(f"⚠️ ログインまたは実行エラー: {e}")

if __name__ == "__main__":
    load_dotenv()
    run_once()