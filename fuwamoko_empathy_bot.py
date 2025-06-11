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
import cv2
import numpy as np

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
    # キーワード定義
    NG_WORDS = [
        "加工肉", "ハム", "ソーセージ", "ベーコン", "サーモン", "たらこ", "明太子",
        "パスタ", "ラーメン", "寿司", "うどん", "sushi", "sashimi", "salmon",
        "meat", "bacon", "ham", "sausage", "pasta", "noodle",
        "soft core", "NSFW", "肌色", "下着", "肌見せ", "露出", "胸", "おっぱい", "谷間",
        "肌フェチ", "soft skin", "fetish"
    ]
    EMOTION_TAGS = {
        "fuwamoko": ["ふわふわ", "もこもこ", "もふもふ", "fluffy", "fluff", "fluffball", "ふわもこ",
                     "ぽよぽよ", "やわやわ"],
        "neutral": ["かわいい", "cute", "adorable", "愛しい"],
        "shonbori": ["しょんぼり", "つらい", "かなしい", "さびしい", "疲れた", "へこんだ", "泣きそう"],
        "food": ["肉", "ご飯", "飯", "ランチ", "ディナー", "モーニング", "ごはん",
                 "おいしい", "うまい", "いただきます", "たべた", "ごちそう", "ご馳走",
                 "まぐろ", "刺身", "チーズ", "スナック", "yummy", "delicious", "tasty",
                 "スープ", "味噌汁", "カルボナーラ", "鍋", "麺", "パン", "トースト",
                 "カフェ", "ジュース", "ミルク", "ドリンク", "おやつ", "食事", "朝食", "夕食", "昼食",
                 "酒", "アルコール", "ビール", "ワイン", "酎ハイ", "カクテル", "ハイボール", "梅酒"],
        "nsfw_ng": NG_WORDS,
        "safe_cosmetics": ["コスメ", "メイク", "リップ", "香水", "スキンケア", "ネイル", "爪", "マニキュア",
                           "cosmetics", "makeup", "perfume", "nail"]
    }
    HIGH_RISK_WORDS = ["もちもち", "ぷにぷに"]
    SAFE_CHARACTER = {
        "アニメ": ["アニメ", "漫画", "マンガ", "キャラ", "イラスト", "ファンアート", "推し"],
        "一次創作": ["一次創作", "オリキャラ", "オリジナル", "創作"],
        "二次創作": ["二次創作", "ファンアート", "FA"]
    }
    COSMETICS_TEMPLATES = {
        "リップ": ["このリップ可愛い〜💄💖", "色味が素敵すぎてうっとりしちゃう💋"],
        "香水": ["この香り、絶対ふわもこだよね🌸", "いい匂いがしてきそう〜🌼"],
        "ネイル": ["そのネイル、キラキラしてて最高💅✨", "ふわもこカラーで素敵〜！💖"]
    }
    CHARACTER_TEMPLATES = {
        "アニメ": ["アニメキャラがモフモフ！💕", "まるで夢の世界の住人🌟"],
        "一次創作": ["オリキャラ尊い…🥺✨", "この子だけの世界観があるね💖"],
        "二次創作": ["この解釈、天才すぎる…！🙌", "原作愛が伝わってくる✨"]
    }
    NG_PHRASES = ["投稿:", "ユーザー", "返事:", "お返事ありがとうございます",
                  "フォーラム", "会話", "私は", "名前", "あなた", "○○", "・", "■", "？", "！" * 5]
    reply_examples = [
        "わぁ…リスさんに会えたの？ふわもこだぁ…🧸💕",
        "夢の中でも癒しがいっぱいだね🌙☁️",
        "リスさんとお昼寝…ぎゅってしたい…♡",
        "きゅん…それ、絶対ふわもこ確定だよ🦝✨"
    ]

    if any(word.lower() in text.lower() for word in NG_WORDS):
        print(f"🛠️ DEBUG: NGワード検出: {text[:40]}")
        return random.choice(MOGUMOGU_TEMPLATES_JP) if lang == "ja" else random.choice(MOGUMOGU_TEMPLATES_EN)

    if not text.strip():
        text = "もふもふの動物の画像だよ〜"

    # プロンプト
    prompt = (
        f"あなたは癒し系でふわもこなマスコットです。\n"
        f"以下を参考に、心がほっこりする短い返信をしてください（40文字以内が目標）:\n"
        f"例: {reply_examples[0]}\n"
        f"例: {reply_examples[1]}\n"
        f"投稿: {text[:60]}\n"
        "ふわもこ返信:"
    )
    
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=140).to(model.device)
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
        reply = re.sub(r'^(.*?あなたは癒し系でふわもこなマスコットです。.*?ふわもこ返信:\s*|\s*投稿:.*?\s*ふわもこ返信:\s*|\s*ふわもこ返信:\s*|\s*例:.*?\s*例:.*?\s*投稿:.*?\s*ふわもこ返信:\s*|\s*投稿:\s*.*?)\s*', '', reply, flags=re.IGNORECASE | re.DOTALL).strip()
        reply = re.sub(r'🧸{3,}|�|■.*?■|フォーラム|会話|ユーザー|投稿|返事|お返事ありがとうございます|私は|名前|あなた|○○|・|？|！{5,}', '', reply).strip()
        if reply and 4 <= len(reply) <= 50 and not any(bad in reply for bad in NG_PHRASES):
            print(f"✅ SUCCESS: AI生成成功: {reply}")
            logging.debug(f"AI生成成功: {reply}")
            return reply
        else:
            print(f"💥 不適切な生成っぽいのでスキップ: {reply[:40]}")
            logging.warning(f"不適切な生成: {reply[:40]}")
    except Exception as e:
        print(f"⚠️ ERROR: AI生成エラー: {e}")
        logging.error(f"AI生成エラー: {e}")

    # テンプレ分類
    NORMAL_TEMPLATES_JP = [
        "うんうん、かわいいね！癒されたよ🐾💖",
        "よかったね〜！ふわふわだね🌸🧸",
        "えへっ、モフモフで癒しMAX！💞",
        "うわっ！可愛すぎるよ🐾🌷",
        "ふわふわだね、元気出た！💫🧸"
    ]
    SHONBORI_TEMPLATES_JP = [
        "そっか…ぎゅーってしてあげるね🐾💕",
        "元気出してね、ふわもこパワー送るよ！🧸✨",
        "つらいときこそ、ふわふわに包まれて…🐰☁️",
        "無理しないでね、そっと寄り添うよ🦡🌸"
    ]
    MOGUMOGU_TEMPLATES_JP = [
        "うーん🐾 美味しそう？ふわもこかな？😸",
        "もぐもぐ？ふわもこも仲間だ！🐶💖",
        "みりん！お腹空いた？ふわふわだよ🍡"
    ]
    NORMAL_TEMPLATES_EN = [
        "Wow, so cute! Feels good~ 🐾💖",
        "Nice! So fluffy~ 😺💕",
        "Great! So healing! 🦊💖",
        "Amazing! Thanks for the fluff! 🐾🌸"
    ]
    MOGUMOGUS_TEMPLATES_EN = [
        "Yummy? But fluffy too? 🐾💕",
        "Nom nom! Fluffy vibes! 🐰🌟",
        "Tasty? Let’s stay cuddly! 🦝💖�"
    ]

    if any(word in text.lower() for word in EMOTION_TAGS["shonbori"]):
        return random.choice(SHONBORI_TEMPLATES_JP) if lang == "ja" else random.choice(NORMAL_TEMPLATES_EN)
    elif any(word.lower() in text.lower() for word in EMOTION_TAGS["safe_cosmetics"]):
        for key in COSMETICS_TEMPLATES:
            if key.lower() in text.lower():
                return random.choice(COSMETICS_TEMPLATES[key])
        return random.choice(COSMETICS_TEMPLATES["リップ"]) if lang == "ja" else random.choice(NORMAL_TEMPLATES_EN)
    elif any(any(word in text.lower() for word in sublist) for sublist in SAFE_CHARACTER.values()):
        for cat, keywords in SAFE_CHARACTER.items():
            if any(word in text.lower() for word in keywords):
                return random.choice(CHARACTER_TEMPLATES[cat"])
        return random.choice(CHARACTER_TEMPLATES["アニメ"]) if lang == "ja" else random.choice(NORMAL_TEMPLATES_EN)
    else:
        return random.choice(NORMAL_TEMPLATES_JP) if lang == "ja" else random.choice(NORMAL_TEMPLATES_EN)

def check_skin_ratio(image_data):
    try:
        if not hasattr(image_data, 'image') or not hasattr(image_data.image, 'ref') or not hasattr(image_data.image.ref, 'link'):
            return 0.0
        cid = image_data.image.ref.link
        img = download_image_from_blob(cid, None)
        if img is None:
            return 0.0

        img = img.convert("RGB")
        img_np = np.array(img)
        hsv = cv2.cvtColor(img_np, cv2.COLOR_RGB2HSV)

        lower_skin = np.array([0, 30, 50], dtype=np.uint8)
        upper_skin = np.array([20, 180, 255], dtype=np.uint8)

        skin_mask = cv2.inRange(hsv, lower_skin, upper_skin)
        skin_area = np.sum(skin_mask > 0)
        total_area = img_np.shape[0] * img_np.shape[1]

        ratio = skin_area / total_area
        print(f"🛠️ DEBUG: Skin ratio detected: {ratio}")
        logging.debug(f"Skin ratio: {ratio}")
        return ratio
    except Exception as e:
        print(f"⚠️ ERROR: 肌色比率チェックエラー: {e}")
        logging.error(f"肌色比率チェックエラー: {e}")
        return 0.0

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
            print(f"✅ SUCCESS: CDN画像取得成功！ URL: {url}")
            logging.debug(f"CDN画像取得成功: {url}")
            return Image.open(BytesIO(response.content))
        except requests.exceptions.RequestException as e:
            print(f"⚠️ ERROR: CDN取得失敗: {url} - {e}")
            logging.error(f"CDN取得失敗: {url} - {e}")
            continue
    
    if client and did:
        try:
            blob = client.com.atproto.repo.get_blob(did=did, cid=cid)
            print("✅ SUCCESS: Blob API画像取得成功！")
            logging.debug("Blob API画像取得成功")
            return Image.open(BytesIO(blob.data))
        except Exception as e:
            print(f"⚠️ ERROR: Blob API取得失敗: {e}")
            logging.error(f"Blob API取得失敗: {e}")
    
    print("❌ ERROR: 画像取得失敗")
    logging.debug("画像取得失敗")
    return None

def process_image(image_data, text="", client=None, post=None):
    if not hasattr(image_data, 'image') or not hasattr(image_data.image, 'ref') or not hasattr(image_data.image.ref, 'link'):
        print("❌ ERROR: 画像データ構造エラー")
        logging.debug("画像データ構造エラー")
        return False

    cid = image_data.image.ref.link
    try:
        author_did = post.post.author.did if post and hasattr(post, 'post') else None
        img = download_image_from_blob(cid, client, did=author_did)
        if img is None:
            print("❌ ERROR: 画像ダウンロード失敗のため画像処理スキップ")
            logging.debug("画像ダウンロード失敗のため画像処理スキップ")
            return False

        img = img.resize((50, 50))
        colors = img.getdata()
        color_counts = Counter(colors)
        common_colors = color_counts.most_common(5)

        fluffy_count = 0
        total_colors = 0
        for color in common_colors:
            r, g, b = color[0][:3]
            total_colors += 1
            if (r > 200 and g > 200 and b > 200) or \
               (r > 220 and g < 170 and b > 200) or \
               (r > 200 and g > 180 and b < 180):
                fluffy_count += 1
        
        skin_ratio = check_skin_ratio(image_data)
        if skin_ratio > 0.2:
            print("🌀 肌色比率多すぎてスキップ")
            logging.debug("肌色比率多すぎ:スキップ")
            return False

        check_text = text.lower()
        if any(word in check_text for word in HIGH_RISK_WORDS):
            if skin_ratio < 0.2 and fluffy_count >= 2:
                print("🎉 SUCCESS: 高リスクワードだが条件クリア")
                logging.debug("高リスクワードだが条件クリア")
                return True
            else:
                print("🌀 高リスクワード＋条件不一致でスキップ")
                logging.debug("高リスクワード＋条件不一致:スキップ")
                return False

        if fluffy_count >= 2 and total_colors >= 3:
            print("🎉 SUCCESS: ふわもこ色検出（複数カラー）！")
            logging.debug("ふわもこ色検出（複数カラー）")
            return True
        else:
            print("🌀 単色または条件不足でスキップ")
            return False

        if any(pos in check_text for pos in EMOTION_TAGS["fuwamoko"]):
            print("🎉 FUWAMOKOキーワードヒット")
            logging.debug("FUWAMOKOキーワード検出")
            return True
        if any(neu in check_text for neu in EMOTION_TAGS["neutral"]) and image_data is None:
            print("🌀 中立ワードのみ＋画像なし。スキップ")
            return False

        return False
    except Exception as e:
        print(f"⚠️ ERROR: 画像解析エラー: {e}")
        logging.error(f"画像解析エラー: {e}")
        return False

def is_quoted_repost(post):
    try:
        actual_post = post.post if hasattr(post, 'post') else post
        record = getattr(actual_post, 'record', None)
        if record and hasattr(record, 'embed') and record.embed:
            embed = record.embed
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

def is_priority_post(text):
    return "@mirinchuuu" in text.lower()

def is_reply_to_self(post):
    reply = getattr(post.record, "reply", None) if hasattr(post, 'record') else None
    if reply and hasattr(reply, "parent") and hasattr(reply.parent, "author"):
        return reply.parent.author.handle == HANDLE
    return False

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
                if content.strip():
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
            load_fuwamoko_uris()
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

def has_image(post):
    actual_post = post.post if hasattr(post, 'post') else post
    record = getattr(actual_post, 'record', None)
    if not record or not hasattr(record, 'embed'):
        return False
    embed = record.embed
    return (hasattr(embed, 'images') and embed.images) or \
           (hasattr(embed, 'record') and hasattr(embed.record, 'embed') and hasattr(embed.record.embed, 'images')) or \
           (getattr(embed, '$type', '') == 'app.bsky.embed.recordWithMedia' and hasattr(embed, 'media') and hasattr(embed.media, 'images'))

def process_post(post, client, fuwamoko_uris, reposted_uris):
    try:
        actual_post = post.post if hasattr(post, 'post') else post
        uri = str(actual_post.uri)
        post_id = uri.split('/')[-1]
        
        text = getattr(actual_post.record, "text", "") if hasattr(actual_post, 'record') and hasattr(actual_post.record, 'text') else ""

        is_reply = getattr(actual_post.record, "reply", None) is not None if hasattr(actual_post, 'record') else False
        if is_reply and not (is_priority_post(text) or is_reply_to_self(post)):
            print(f"⏩ リプライスキップ (非@mirinchuuu/非自分宛): {text[:40]}")
            logging.debug(f"リプライスキップ: {post_id}")
            return False

        print(f"🛠️ DEBUG: Processing post {post_id} by @{actual_post.author.handle}, HANDLE={HANDLE}")
        logging.debug(f"Processing post {post_id} by @{actual_post.author.handle}, HANDLE={HANDLE}")
        if uri in fuwamoko_uris:
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

        author = actual_post.author.handle
        indexed_at = actual_post.indexed_at

        if not has_image(post):
            print(f"⏭️ SKIP: 画像なしなのでスキップ: {post_id}")
            logging.debug(f"画像なし: {post_id}")
            return False

        image_data_list = []
        embed = getattr(actual_post.record, 'embed', None) if hasattr(actual_post, 'record') and hasattr(actual_post.record, 'embed') else None

        if embed:
            if hasattr(embed, 'images') and embed.images:
                image_data_list = embed.images
            elif hasattr(embed, 'record') and hasattr(embed.record, 'embed') and hasattr(embed.record.embed, 'images'):
                image_data_list = embed.record.embed.images
            elif getattr(embed, '$type', '') == 'app.bsky.embed.recordWithMedia':
                if hasattr(embed, 'media') and hasattr(embed.media, 'images'):
                    image_data_list = embed.media.images

        if not is_mutual_follow(client, author):
            print(f"⏭️ SKIP: 非相互フォローなのでスキップ: {post_id} (Author: @{author})")
            logging.debug(f"非相互フォロー: {post_id} (Author: @{author})")
            return False

        if image_data_list:
            for i, image_data in enumerate(image_data_list):
                print(f"🛠️ DEBUG: Processing image {i+1} of {len(image_data_list)} for post {post_id}")
                if process_image(image_data, text, client=client, post=post):
                    if random.random() >= 0.5:
                        print(f"⏭️ SKIP: ランダムスキップ（確率50%）: {post_id}")
                        logging.debug(f"ランダムスキップ（確率50%）: {post_id}")
                        save_fuwamoko_uri(uri, indexed_at)
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
                    print(f"⏭️ SKIP: ふわもこ画像でないのでスキップ: {post_id} (image {i+1})")
                    logging.debug(f"ふわもこ画像でない: {post_id} (image {i+1})")
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
            time.sleep(random.uniform(10, 20))

    except Exception as e:
        print(f"⚠️ ERROR: 実行エラー: {e}")
        logging.error(f"実行エラー: {e}")

if __name__ == "__main__":
    load_dotenv()
    run_once()