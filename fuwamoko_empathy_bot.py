# 🔽 📦 Pythonの標準ライブラリ
from datetime import datetime, timezone
import os
import json
import time
import random

# 🔽 🌱 外部ライブラリ
from dotenv import load_dotenv
from transformers import AutoModelForCausalLM, AutoTokenizer

# 🔽 📡 atproto関連
from atproto import Client, models
from atproto_client.models import AppBskyFeedPost
from atproto_client.exceptions import InvokeTimeoutError

# 🔽 🧠 Transformers用設定
MODEL_NAME = "cyberagent/open-calm-1b"  # モデル名
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForCausalLM.from_pretrained(MODEL_NAME)

# 環境変数読み込み
load_dotenv()  # .envファイルから読み込み（なくてもSecretsで動作）
HANDLE = os.environ.get("HANDLE")
APP_PASSWORD = os.environ.get("APP_PASSWORD")

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
        # 相手のフォロー一覧を取得（相手が誰をフォローしているか）
        their_follows = client.app.bsky.graph.get_follows(params={"actor": handle, "limit": 100})
        their_following = [f.handle for f in their_follows.follows]

        # 自分（HANDLE）のフォロー一覧を取得
        my_follows = client.app.bsky.graph.get_follows(params={"actor": os.environ.get("HANDLE"), "limit": 100})
        my_following = [f.handle for f in my_follows.follows]

        return os.environ.get("HANDLE") in their_following and handle in my_following
    except Exception as e:
        print(f"⚠️ 相互フォロー判定エラー: {e}")
        return False

def process_image(image_url):
    # 簡易実装：画像URLをテキストとして扱う（本格的には画像処理ライブラリ必要）
    return "ふわふわ" in image_url or "もこもこ" in image_url or "かわいい" in image_url  # 仮判定

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
        profile = client.app.bsky.actor.getProfile(actor=handle)
        bio = profile.display_name.lower() + " " + getattr(profile, "description", "").lower()
        if any(kw in bio for kw in ["日本語", "日本", "にほん"]):
            return "ja"
        elif any(kw in bio for kw in ["english", "us", "uk"]):
            return "en"
        return "ja"  # デフォルト
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
        print(f"⏩ 履歴保存スキップ（1日1回）: {normalized_uri}")
        return
    try:
        with open(FUWAMOKO_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{normalized_uri}|{datetime.now(timezone.utc).isoformat()}\n")
        fuwamoko_uris[normalized_uri] = datetime.now(timezone.utc)
        print(f"💾 履歴保存: {normalized_uri}")
    except Exception as e:
        print(f"⚠️ 履歴保存エラー: {e}")

def run_once():
    try:
        client = Client()
        client.login(HANDLE, APP_PASSWORD)
        print("📨 ふわもこ共感Bot起動中…")

        timeline = client.app.bsky.feed.get_timeline(params={"limit": 20})
        feed = timeline.feed

        load_fuwamoko_uris()
        reposted_uris = load_reposted_uris_for_check()

        for post in feed:
            time.sleep(random.uniform(5, 15))
            text = getattr(post.post.record, "text", "")
            uri = str(post.post.uri)
            post_id = uri.split('/')[-1]
            author = post.post.author.handle
            embed = getattr(post.post.record, "embed", None)

            if uri in fuwamoko_uris or author == HANDLE or is_quoted_repost(post) or post_id in reposted_uris:
                continue

            if embed and hasattr(embed, 'images') and is_mutual_follow(client, author):
                image_data = embed.images[0]
                print(f"DEBUG: Image data = {image_data.__dict__}")  # 利用可能な属性を確認
                image_url = getattr(image_data, 'thumbnail', getattr(image_data, 'url', ''))
                if process_image(image_url) and random.random() < 0.5:  # 50%確率
                    lang = detect_language(client, author)
                    reply_text = open_calm_reply(image_url, text, lang=lang)
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

if __name__ == "__main__":
    load_dotenv()
    run_once()