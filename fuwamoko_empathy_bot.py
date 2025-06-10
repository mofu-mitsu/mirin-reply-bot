# 🔽 📦 Pythonの標準ライブラリ
from datetime import datetime, timezone
import os
import time
import random
import requests
from io import BytesIO
import filelock
import re
import logging

# 🔽 🌱 外部ライブラリ
from dotenv import load_dotenv
from transformers import AutoModelForCausalLM, AutoTokenizer
from PIL import Image
from collections import Counter
import torch

# 🔽 📡 atproto関連
from atproto import Client, models

# ロギング設定
logging.basicConfig(filename='debug.log', level=logging.DEBUG, format='%(asctime)s %(message)s')
logging.getLogger().addHandler(logging.StreamHandler())  # コンソール出力

# 🔽 🧠 Transformers用設定
MODEL_NAME = "cyberagent/open-calm-small"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, cache_dir=".cache", force_download=True)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    cache_dir=".cache",
    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
    device_map="auto",
    force_download=True
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
    instruction = (
        "あなたはふわもこ系のやさしいBotです。"
        "以下のユーザーの投稿に、親しみやすく共感して短く返信してください。"
        "返信にはかわいい絵文字を1つか2つ入れてください。"
        "返信はカジュアルで口語的な日本語にしてください。"
    )
    prompt = f"{instruction}\n投稿:「{text[:80]}」\n返事: "
    
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=120).to(model.device)  # max_length調整
    try:
        outputs = model.generate(
            **inputs,
            max_new_tokens=60,
            pad_token_id=tokenizer.pad_token_id,
            do_sample=True,
            temperature=0.7,
            top_k=40,
            top_p=0.9
        )
        reply = tokenizer.decode(outputs[0], skip_special_tokens=True).strip()
        reply = re.sub(r'^.*?返事:\s*', '', reply)  # 「返事:」から抜き出し
        reply = re.sub(r'🧸{3,}|�|■.*?■', '', reply)  # 過多・文字化け除去
        reply = reply.strip()
        print(f"🛠️ DEBUG: AI generated reply: {reply}")
        logging.debug(f"AI generated reply: {reply}")
        if not reply or len(reply) < 4 or "漫画家の顔" in reply or "管制官" in reply:
            print("🛠️ DEBUG: AI reply invalid, using template")
            logging.debug("AI reply invalid, using template")
            reply = None
    except Exception as e:
        print(f"⚠️ ERROR: AI生成エラー: {e}")
        logging.error(f"AI生成エラー: {e}")
        reply = None
    
    if lang == "ja":
        return reply or random.choice([
            "え、待って！このふわもこ、みりんてゃの心臓バクバク！🧸💥",
            "きゃー！このモフモフ、みりんてゃの癒し100％！💖",
            "ふwaふwaすぎてみりんてゃ飛んじゃう！🌸🧸",
            "モフモフ天国！みりんてゃの心、奪われた！💞",
            "このふwaもこ、みりんてゃの夢そのもの！🧸✨",
            "うわっ！この可愛さ、みりんてゃ倒れそう！💖",
            "ふわふwaハグしたい！みりんてゃの愛全開！🌷",
            "このモフモフ、みりんてゃの癒し爆発！🧸💫",
            "ピンクと白の奇跡！みりんてゃキュン死！💕",
            "ふwaもこすぎてみりんてゃの心がモフっと！🌸",
            "このふwaもこ、みりんてゃの愛が爆発！💖",
            "モフモフすぎてみりんてゃの心が溶ける！🧸",
            "ふwaふwa天国！みりんてゃの癒しMAX！🌷",
            "この可愛さ、みりんてゃの心を鷲づかみ！💞",
            "ふwaもこ愛！みりんてゃのハート直撃！🧸💥"
        ])
    else:
        return reply or random.choice([
            "Wow! So fluffy~ Mirin is obsessed! 💕",
            "Oh my! This cuteness kills me~ Mirin loves it! 🥰",
            "Amazing! Fluffy vibes healing my soul! 🌸",
            "This fluff is unreal! Mirin’s heart skips! 💖",
            "So soft! Mirin can’t handle this cuteness! 🧸",
            "Fluffy perfection! Mirin’s in love! 💞"
        ])

def is_mutual_follow(client, handle):
    try:
        their_follows = client.get_follows(actor=handle, limit=100).follows
        their_following = {f.handle for f in their_follows}
        my_follows = client.get_follows(actor=HANDLE, limit=100).follows
        my_following = {f.handle for f in my_follows}
        return HANDLE in their_following and handle in my_following
    except Exception as e:
        print(f"⚠️ ERROR: 相互フォロー判定エラー: {e}")
        logging.error(f"相互フォロー判定エラー: {e}")
        return False

def download_image_from_blob(cid, client, did=None):
    cdn_urls = [
        f"https://cdn.bsky.app/img/feed_thumbnail/plain/{did}/{cid}@jpeg" if did else None,
        f"https://cdn.bsky.app/img/feed_full/plain/{did}/{cid}@jpeg" if did else None,
        f"https://cdn.bsky.app/img/feed_thumbnail/plain/{cid}@jpeg",
        f"https://cdn.bsky.app/img/feed_full/plain/{cid}@jpeg",
    ]
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for url in [u for u in cdn_urls if u]:
        try:
            response = requests.get(url, stream=True, timeout=10, headers=headers)
            response.raise_for_status()
            print("✅ SUCCESS: CDN画像取得成功！")
            logging.debug("CDN画像取得成功")
            return Image.open(BytesIO(response.content))
        except requests.exceptions.RequestException:
            pass
    
    if client and did:
        try:
            blob = client.com.atproto.repo.get_blob(did=did, cid=cid)
            print("✅ SUCCESS: Blob API画像取得成功！")
            logging.debug("Blob API画像取得成功")
            return Image.open(BytesIO(blob.data))
        except Exception:
            pass
    
    print("❌ ERROR: 画像取得失敗")
    logging.debug("画像取得失敗")
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
            print("🎉 SUCCESS: ふわもこ色検出！")
            logging.debug("ふわもこ色検出")
            return True

        check_text = text.lower()
        keywords = ["ふわふわ", "もこもこ", "かわいい", "fluffy", "cute", "soft", "もふもふ", "愛しい", "癒し", "たまらん", "adorable"]
        if any(keyword in check_text for keyword in keywords):
            print("🎉 SUCCESS: キーワード検出！")
            logging.debug("キーワード検出")
            return True

        return False
    except Exception as e:
        print(f"⚠️ ERROR: 画像解析エラー: {e}")
        logging.error(f"画像解析エラー: {e}")
        return False

def is_quoted_repost(post):
    try:
        actual_post_record = post.post.record if hasattr(post, 'post') else post.record
        if hasattr(actual_post_record, 'embed') and actual_post_record.embed:
            embed = actual_post_record.embed
            print(f"🛠️ DEBUG: Checking embed for quoted repost: {embed}")
            logging.debug(f"Checking embed for quoted repost: {embed}")
            if hasattr(embed, 'record') and embed.record:
                print("🛠️ DEBUG: Found quoted repost (record)")
                logging.debug("Found quoted repost (record)")
                return True
            elif hasattr(embed, 'record') and hasattr(embed.record, 'record') and embed.record.record:
                print("🛠️ DEBUG: Found quoted repost (recordWithMedia)")
                logging.debug("Found quoted repost (recordWithMedia)")
                return True
        return False
    except Exception as e:
        print(f"⚠️ ERROR: 引用リポストチェックエラー: {e}")
        logging.error(f"引用リポストチェックエラー: {e}")
        return False

def load_reposted_uris_for_check():
    REPOSTED_FILE = "reposted_uris.txt"
    if os.path.exists(REPOSTED_FILE):
        try:
            with open(REPOSTED_FILE, 'r', encoding='utf-8') as f:
                uris = set(line.strip() for line in f if line.strip())
                print(f"✅ SUCCESS: 読み込んだ reposted_uris: {len(uris)}件")
                logging.debug(f"読み込んだ reposted_uris: {len(uris)}件")
                return uris
        except Exception as e:
            print(f"⚠️ ERROR: reposted_uris読み込みエラー: {e}")
            logging.error(f"reposted_uris読み込みエラー: {e}")
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
    except Exception as e:
        print(f"⚠️ ERROR: 言語判定エラー: {e}")
        logging.error(f"言語判定エラー: {e}")
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
        print(f"⚠️ ERROR: URI正規化エラー: {e}")
        logging.error(f"URI正規化エラー: {e}")
        return uri

def load_fuwamoko_uris():
    global fuwamoko_uris
    fuwamoko_uris.clear()
    if os.path.exists(FUWAMOKO_FILE):
        try:
            with open(FUWAMOKO_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
                print(f"📦 INFO: fuwamoko_empathy_uris.txt size: {len(content)} bytes")
                logging.debug(f"fuwamoko_empathy_uris.txt size: {len(content)} bytes")
                if content.strip():  # 空でない場合のみ処理
                    for line in content.splitlines():
                        if line.strip():
                            uri, timestamp = line.strip().split("|", 1)
                            fuwamoko_uris[normalize_uri(uri)] = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                print(f"📦 INFO: Loaded {len(fuwamoko_uris)} fuwamoko uris from {FUWAMOKO_FILE}")
                logging.debug(f"Loaded {len(fuwamoko_uris)} fuwamoko uris")
        except Exception as e:
            print(f"⚠️ ERROR: 履歴読み込みエラー: {e}")
            logging.error(f"履歴読み込みエラー: {e}")

def save_fuwamoko_uri(uri, indexed_at):
    global fuwamoko_uris
    normalized_uri = normalize_uri(uri)
    lock = filelock.FileLock(FUWAMOKO_LOCK, timeout=10.0)
    try:
        with lock:
            if os.path.exists(FUWAMOKO_FILE):
                with open(FUWAMOKO_FILE, 'r', encoding='utf-8') as f:
                    content = f.read()
                with open(FUWAMOKO_FILE + '.bak', 'w', encoding='utf-8') as f:
                    f.write(content)
            if normalized_uri in fuwamoko_uris and (datetime.now(timezone.utc) - fuwamoko_uris[normalized_uri]).total_seconds() < 24 * 3600:
                print(f"⏭️ SKIP: 履歴保存スキップ（24時間以内）: {normalized_uri.split('/')[-1]}")
                logging.debug(f"履歴保存スキップ（24時間以内）: {normalized_uri}")
                return
            if isinstance(indexed_at, str):
                indexed_at = datetime.fromisoformat(indexed_at.replace("Z", "+00:00"))
            with open(FUWAMOKO_FILE, 'a', encoding='utf-8') as f:
                f.write(f"{normalized_uri}|{indexed_at.isoformat()}\n")
            fuwamoko_uris[normalized_uri] = indexed_at
            print(f"💾 SUCCESS: 履歴保存: {normalized_uri.split('/')[-1]}")
            logging.debug(f"履歴保存: {normalized_uri}")
            load_fuwamoko_uris()  # 保存後に即再読み込み
    except filelock.Timeout:
        print(f"⚠️ ERROR: ファイルロックタイムアウト: {FUWAMOKO_LOCK}")
        logging.error(f"ファイルロックタイムアウト: {FUWAMOKO_LOCK}")
    except Exception as e:
        print(f"⚠️ ERROR: 履歴保存エラー: {e}")
        logging.error(f"履歴保存エラー: {e}")

def load_session_string():
    try:
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE, 'r', encoding='utf-8') as f:
                return f.read().strip()
        return None
    except Exception as e:
        print(f"⚠️ ERROR: セッション文字列読み込みエラー: {e}")
        logging.error(f"セッション文字列読み込みエラー: {e}")
        return None

def save_session_string(session_str):
    try:
        with open(SESSION_FILE, 'w', encoding='utf-8') as f:
            f.write(session_str)
    except Exception as e:
        print(f"⚠️ ERROR: セッション文字列保存エラー: {e}")
        logging.error(f"セッション文字列保存エラー: {e}")

def process_post(post, client, fuwamoko_uris, reposted_uris):
    try:
        actual_post = post.post if hasattr(post, 'post') else post
        uri = str(actual_post.uri)
        post_id = uri.split('/')[-1]
        
        print(f"🛠️ DEBUG: Processing post {post_id} by @{actual_post.author.handle}, HANDLE={HANDLE}")
        logging.debug(f"Processing post {post_id} by @{actual_post.author.handle}, HANDLE={HANDLE}")
        if uri in fuwamoko_uris:  # チェックを先頭に
            print(f"⏭️ SKIP: 既に返信済みの投稿なのでスキップ: {post_id}")
            logging.debug(f"既に返信済みの投稿: {post_id}")
            return False
        if actual_post.author.handle == HANDLE:
            print(f"⏭️ SKIP: 自分の投稿なのでスキップ: {post_id} (Author: @{actual_post.author.handle})")
            logging.debug(f"自分の投稿: {post_id} (Author: @{actual_post.author.handle})")
            return False
        if is_quoted_repost(post):
            print(f"⏭️ SKIP: 引用リポストなのでスキップ: {post_id}")
            logging.debug(f"引用リポスト: {post_id}")
            return False
        if post_id in reposted_uris:
            print(f"⏭️ SKIP: リポスト済みURIなのでスキップ: {post_id}")
            logging.debug(f"リポスト済みURI: {post_id}")
            return False

        text = getattr(actual_post.record, "text", "")
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
            print(f"⏭️ SKIP: 画像なしなのでスキップ: {post_id}")
            logging.debug(f"画像なし: {post_id}")
            return False

        if not is_mutual_follow(client, author):
            print(f"⏭️ SKIP: 非相互フォローなのでスキップ: {post_id} (Author: @{author})")
            logging.debug(f"非相互フォロー: {post_id} (Author: @{author})")
            return False

        if image_data_list:
            image_data = image_data_list[0]
            if process_image(image_data, text, client=client, post=post):
                if random.random() >= 0.5:  # 50%スキップ
                    print(f"⏭️ SKIP: ランダムスキップ（確率50%）: {post_id}")
                    logging.debug(f"ランダムスキップ（確率50%）: {post_id}")
                    save_fuwamoko_uri(uri, indexed_at)  # スキップ時も保存
                    return False
                lang = detect_language(client, author)
                reply_text = open_calm_reply("", text, lang=lang)
                reply_ref = models.AppBskyFeedPost.ReplyRef(
                    root=models.ComAtprotoRepoStrongRef.Main(uri=uri, cid=actual_post.cid),
                    parent=models.ComAtprotoRepoStrongRef.Main(uri=uri, cid=actual_post.cid)
                )
                print(f"🛠️ DEBUG: Sending post to @{author} with text: {reply_text}")
                logging.debug(f"Sending post to @{author} with text: {reply_text}")
                client.send_post(
                    text=reply_text,
                    reply_to=reply_ref
                )
                save_fuwamoko_uri(uri, indexed_at)
                print(f"✅ SUCCESS: 返信しました → @{author}")
                logging.debug(f"返信成功: @{author}")
                return True
            else:
                print(f"⏭️ SKIP: ふわもこ画像でないのでスキップ: {post_id}")
                logging.debug(f"ふわもこ画像でない: {post_id}")
        return False
    except Exception as e:
        print(f"⚠️ ERROR: 投稿処理エラー: {e}")
        logging.error(f"投稿処理エラー: {e}")
        return False

def run_once():
    try:
        client = Client()
        session_str = load_session_string()
        if session_str:
            client.login(session_string=session_str)
            print(f"🚀 START: ふわもこBot起動！ セッション再利用")
            logging.info("Bot started: session reuse")
        else:
            client.login(HANDLE, APP_PASSWORD)
            session_str = client.export_session_string()
            save_session_string(session_str)
            print(f"🚀 START: ふわもこBot起動！ 新規セッション")
            logging.info("Bot started: new session")

        print(f"🛠️ DEBUG: Bot HANDLE={HANDLE}")
        logging.debug(f"Bot HANDLE={HANDLE}")
        load_fuwamoko_uris()
        reposted_uris = load_reposted_uris_for_check()

        timeline = client.get_timeline(limit=50)
        feed = timeline.feed
        for post in sorted(feed, key=lambda x: x.post.indexed_at, reverse=True):
            try:
                thread_response = client.get_post_thread(uri=str(post.post.uri), depth=2)
                process_post(thread_response.thread, client, fuwamoko_uris, reposted_uris)
            except Exception as e:
                print(f"⚠️ ERROR: get_post_threadエラー: {e} (URI: {post.post.uri})")
                logging.error(f"get_post_threadエラー: {e} (URI: {post.post.uri})")
            time.sleep(random.uniform(2, 5))

    except Exception as e:
        print(f"⚠️ ERROR: 実行エラー: {e}")
        logging.error(f"実行エラー: {e}")

if __name__ == "__main__":
    load_dotenv()
    run_once()