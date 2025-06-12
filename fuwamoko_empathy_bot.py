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
from urllib.parse import quote, unquote
from PIL import Image, UnidentifiedImageError, ImageFile

# 🔽 🌱 外部ライブラリ
from dotenv import load_dotenv
from transformers import AutoModelForCausalLM, AutoTokenizer
from collections import Counter
import torch

# 🔽 📡 atproto関連
from atproto import Client, models

# ロギング設定
logging.basicConfig(filename='debug.log', level=logging.DEBUG, format='%(asctime)s %(message)s', encoding='utf-8')
logging.getLogger().addHandler(logging.StreamHandler())

# PILのエラー抑制
ImageFile.LOAD_TRUNCATED_IMAGES = True

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

# 🔽 保護設定（チャッピー監査済み）
LOCK_CONFIG = {
    "TEMPLATES": True,
    "EMOTION_TAGS": True,
    "HIGH_RISK_WORDS": True,
    "SAFE_CHARACTER": True,
    "COSMETICS_TEMPLATES": True,
    "CHARACTER_TEMPLATES": True
}

# 🔽 グローバル辞書初期化（チャッピー保護）
try:
    _ = globals()["HIGH_RISK_WORDS"]
except KeyError:
    logging.error("⚠️⚖️ HIGH_RISK_WORDSが未定義。デフォルトを再注入します。")
    globals()["HIGH_RISK_WORDS"] = [
        "もちもち", "ぷにぷに", "ぷよぷよ", "やわらかい", "むにゅむにゅ", "エロ", "えっち",
        "nude", "nsfw", "naked", "lewd", "18+", "sex", "uncensored"
    ]

try:
    _ = globals()["EMOTION_TAGS"]
except KeyError:
    logging.error("⚠️⚖️ EMOTION_TAGSが未定義。デフォルトを再注入します。")
    globals()["EMOTION_TAGS"] = {
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
        "safe_cosmetics": ["コスメ", "メイク", "リップ", "香水", "スキンケア", "ネイル", "爪", "マニキュア",
                           "cosmetics", "makeup", "perfume", "nail"]
    }

try:
    _ = globals()["SAFE_CHARACTER"]
except KeyError:
    logging.error("⚠️⚖️ SAFE_CHARACTERが未定義。デフォルトを再注入します。")
    globals()["SAFE_CHARACTER"] = {
        "アニメ": ["アニメ", "漫画", "マンガ", "キャラ", "イラスト", "ファンアート", "推し"],
        "一次創作": ["一次創作", "オリキャラ", "オリジナル", "創作"],
        "二次創作": ["二次創作", "ファンアート", "FA"]
    }

try:
    _ = globals()["COSMETICS_TEMPLATES"]
except KeyError:
    logging.error("⚠️⚖️ COSMETICS_TEMPLATESが未定義。デフォルトを再注入します。")
    globals()["COSMETICS_TEMPLATES"] = {
        "リップ": ["このリップ可愛い〜💄💖", "色味が素敵すぎてうっとりしちゃう💋"],
        "香水": ["この香り、絶対ふわもこだよね🌸", "いい匂いがしてきそう〜🌼"],
        "ネイル": ["そのネイル、キラキラしてて最高💅✨", "ふわもこカラーで素敵〜💖"]
    }

try:
    _ = globals()["CHARACTER_TEMPLATES"]
except KeyError:
    logging.error("⚠️⚖️ CHARACTER_TEMPLATESが未定義。デフォルトを再注入します。")
    globals()["CHARACTER_TEMPLATES"] = {
        "アニメ": ["アニメキャラがモフモフ！💕", "まるで夢の世界の住人🌟"],
        "一次創作": ["オリキャラ尊い…🥺✨", "この子だけの世界観があるね💖"],
        "二次創作": ["この解釈、天才すぎる…！🙌", "原作愛が伝わってくるよ✨"]
    }

def is_fluffy_color(r, g, b):
    """色がふわもこ系（白、ピンク、クリーム、パステルパープル）かを判定"""
    # RGB判定
    if r > 230 and g > 230 and b > 230:  # 白系
        return True
    if r > 220 and g < 100 and b > 180:  # ピンク系
        return True
    if r > 240 and g > 230 and b > 180:  # クリーム色系
        return True
    if r > 220 and b > 220 and abs(r - b) < 30 and g > 200:  # パステルパープル
        return True
    # HSV補強
    hsv = cv2.cvtColor(np.array([[[r, g, b]]], dtype=np.uint8), cv2.COLOR_RGB2HSV)[0][0]
    h, s, v = hsv
    if 200 <= h <= 300 and s < 50 and v > 200:  # パステル系（紫～ピンク）
        return True
    return False

def open_calm_reply(image_url, text="", context="ふわもこ共感", lang="ja"):
    NG_WORDS = globals()["EMOTION_TAGS"].get("nsfw_ng", [
        "加工肉", "ハム", "ソーセージ", "ベーコン", "サーモン", "たらこ", "明太子",
        "パスタ", "ラーメン", "寿司", "うどん", "sushi", "sashimi", "salmon",
        "meat", "bacon", "ham", "sausage", "pasta", "noodle",
        "soft core", "NSFW", "肌色", "下着", "肌見せ", "露出",
        "肌フェチ", "soft skin", "fetish"
    ])
    NG_PHRASES = [
        "投稿:", "ユーザー", "返事:", "お返事ありがとうございます", "フォーラム", "会話",
        "私は", "名前", "あなた", "○○", "・", "■", "!{5,}", r"\?{5,}", r"[!？]{5,}",
        "ふわもこ返信", "例文", "擬音語", "癒し系", "マスクット", "マスケット", "共感", "動物"
    ]

    if LOCK_CONFIG["TEMPLATES"]:
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
            "無理しないでね、そっと寄り添うよ🦗🌸"
        ]
        MOGUMOGU_TEMPLATES_J = [
            "うーん…これは癒しより美味しそう？🐾💖",
            "もぐもぐしてるけど…ふわもこじゃない？🤔",
            "みりんてゃ、お腹空いてきちゃった…食レポ？🍽️💖"
        ]
        NORMAL_TEMPLATES_EN = [
            "Wow, so cute! Feels good~ 🐾💖",
            "Nice! So fluffy~ 🌸🧸",
            "Great! Healing vibes! 💞",
            "Amazing! Thanks for💖! 🦗🌷"
        ]
        MOGUMOGU_TEMPLATES_EN = [
            "Hmmm... looks tasty, but maybe not so fluffy? 🐾💖",
            "So yummy-looking... but a snack or a friend? 🤔🍽️",
            "This might be food, not a fluffy cutie... 🍽️💖",
            "Adorable! But maybe not a fluffy buddy? 🐯💬"
        ]
    else:
        NORMAL_TEMPLATES_JP = ["かわいいね！癒されるよ🐾💖"]
        MOGUMOGU_TEMPLATES_JP = ["美味しそう…でもふわもこ？🤷"]
        NORMAL_TEMPLATES_EN = ["So cute! 🐾💖"]
        MOGUMOGU_TEMPLATES_EN = ["Tasty… but fluffy? 🤷‍♂️"]

    detected_tags = []
    for tag, words in globals()["EMOTION_TAGS"].items():
        if any(word in text.lower() for word in words):
            detected_tags.append(tag)

    if "food" in detected_tags or any(word.lower() in text.lower() for word in NG_WORDS):
        print(f"🦋 DEBUG: NGワード/食事検出: {text[:40]}")
        logging.debug(f"NGワード/食事検出: {text[:40]}")
        return random.choice(MOGUMOGU_TEMPLATES_JP) if lang == "ja" else random.choice(MOGUMOGU_TEMPLATES_EN)
    elif "shonbori" in detected_tags:
        return random.choice(SHONBORI_TEMPLATES_JP) if lang == "ja" else random.choice(NORMAL_TEMPLATES_EN)
    elif "safe_cosmetics" in detected_tags:
        for cosmetic, templates in globals()["COSMETICS_TEMPLATES"].items():
            if cosmetic in text.lower():
                return random.choice(templates)
    elif any(tag in detected_tags for tag in globals()["SAFE_CHARACTER"]):
        for char_type, templates in globals()["CHARACTER_TEMPLATES"].items():
            if any(word in text.lower() for word in globals()["SAFE_CHARACTER"][char_type]):
                return random.choice(templates)

    if not text.strip():
        text = "ふわふわな動物の画像だよ〜🌸"

    prompt = (
        "あなたは癒し系のふわもこマスコットです。\n"
        "以下の例文のように、優しくて心がほっこりする短い返事（40文字以内）をしてください:\n"
        "### 例:\n"
        "- わぁ…もふもふの子に会えたの？🧸💕\n"
        "- 今日もふわふわ癒されるね〜🌙✨\n"
        "- ふわふわな夢で癒される〜♡💖\n"
        f"### 投稿内容:\n{text.strip()[:30]}\n"
        "### ふわもこ返信:"
    )
    
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=140).to(model.device)
    try:
        outputs = model.generate(
            **inputs,
            max_new_tokens=40,
            pad_token_id=tokenizer.pad_token_id,
            do_sample=True,
            temperature=0.7,
            top_k=40,
            top_p=0.9
        )
        reply = tokenizer.decode(outputs[0], skip_special_tokens=True).strip()
        reply = re.sub(r'^.*?###\s*ふわ*も*こ*返信:*\s*', '', reply, flags=re.DOTALL).strip()
        reply = re.sub(r'[■\s]+|(ユーザー|投稿|例文|擬音語|マスクット|マスケット|癒し系|.*?:.*?[:;]|\#.*|[。！？]*)$', '', reply).strip()
        if len(reply) < 4 or len(reply) > 40 or any(re.search(bad, reply.lower()) for bad in NG_PHRASES):
            print(f"💥 SKIP理由: 長さ or NGフレーズ: 「{reply[:60]}」")
            logging.warning(f"SKIP理由: 長さ or NGフレーズ: {reply[:60]}")
            return random.choice(NORMAL_TEMPLATES_JP) if lang == "ja" else random.choice(NORMAL_TEMPLATES_EN)
        print(f"✅ SUCCESS: AI生成: {reply}")
        logging.debug(f"AI生成: {reply}")
        return reply
    except Exception as e:
        print(f"⚠️ ERROR: AI生成エラー: {type(e).__name__}: {e}")
        logging.error(f"AI生成エラー: {type(e).__name__}: {e}")
        return random.choice(NORMAL_TEMPLATES_JP) if lang == "ja" else random.choice(NORMAL_TEMPLATES_EN)

def extract_valid_cid(ref) -> str | None:
    try:
        cid_candidate = str(ref.link) if hasattr(ref, 'link') else str(ref)
        if re.match(r'^baf[a-z0-9]{40,60}$', cid_candidate):
            return cid_candidate
        print(f"⚠️ 無効なCID検出: {cid_candidate}")
        logging.error(f"無効なCID: {cid_candidate}")
        return None
    except Exception as e:
        print(f"⚠️ CID抽出エラー: {type(e).__name__}: {e}")
        logging.error(f"CID抽出エラー: {type(e).__name__}: {e}")
        return None

def check_skin_ratio(image_data, client=None):
    try:
        if not hasattr(image_data, 'image') or not hasattr(image_data.image, 'ref'):
            print("❌ ERROR: 画像データ構造エラー")
            logging.debug("画像データ構造エラー")
            return 0.0
        cid = extract_valid_cid(image_data.image.ref)
        if not cid:
            return 0.0
        img = download_image_from_blob(cid, client, did=None)
        if img is None:
            print("❌ ERROR: 画像ダウンロード不可")
            logging.debug("画像ダウンロード不可")
            return 0.0

        img_pil = img.convert("RGB")
        img_np = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
        if img_np is None or img_np.size == 0:
            print("⚠️ ERROR: 画像データ無効")
            logging.error("画像データ無効")
            return 0.0

        hsv_img = cv2.cvtColor(img_np, cv2.COLOR_BGR2HSV)
        lower = np.array([0, 30, 50], dtype=np.uint8)
        upper = np.array([20, 255, 255], dtype=np.uint8)
        mask = cv2.inRange(hsv_img, lower, upper)
        skin_area = np.sum(mask > 0)
        total_area = img_np.shape[0] * img_np.shape[1]
        ratio = skin_area / total_area if total_area > 0 else 0.0
        print(f"🦋 DEBUG: 肌色比率: {ratio:.2%}")
        logging.debug(f"肌色比率: {ratio:.2%}")
        return ratio
    except Exception as e:
        print(f"⚠️ ERROR: 肌色解析エラー: {type(e).__name__}: {e}")
        logging.error(f"肌色解析エラー: {type(e).__name__}: {e}")
        return 0.0

def is_mutual_follow(client, handle):
    try:
        their_followers = client.get_followers(actor=handle, limit=100).followers
        their_followers = {f.handle for f in their_followers}
        my_followers = client.get_followers(actor=HANDLE, limit=100).followers
        my_followers = {f.handle for f in my_followers}
        return handle in my_followers and HANDLE in their_followers
    except Exception as e:
        print(f"⚠️ ERROR: 相互フォロー判定エラー: {type(e).__name__}: {e}")
        logging.error(f"相互フォロー判定エラー: {type(e).__name__}: {e}")
        return False

def download_image_from_blob(cid, client, did=None):
    if not cid or not re.match(r'^baf[a-z0-9]{40,60}$', cid):
        print(f"⚠️ ERROR: 無効なCID: {cid}")
        logging.error(f"無効なCID: {cid}")
        return None

    # DIDの二重エンコード防止
    did_safe = unquote(did) if did else None
    cdn_urls = [
        f"https://cdn.bsky.app/img/feed_thumbnail/plain/{quote(did_safe)}/{quote(cid)}@jpeg" if did_safe else None,
        f"https://cdn.bsky.app/img/feed_full/plain/{quote(did_safe)}/{quote(cid)}@jpeg" if did_safe else None
    ]
    headers = {"User-Agent": "Mozilla/5.0"}

    for url in [u for u in cdn_urls if u]:
        try:
            print(f"🦊 CDNリクエスト開始: CID={cid}, url={url}")
            logging.debug(f"CDNリクエスト開始: CID={cid}, url={url}")
            response = requests.get(url, headers=headers, timeout=10, stream=True)
            response.raise_for_status()
            print(f"✅ SUCCESS: CDN取得成功: サイズ={len(response.content)} bytes")
            logging.debug(f"CDN取得成功: サイズ={len(response.content)} bytes")
            img_data = BytesIO(response.content)
            try:
                img = Image.open(img_data)
                print(f"✅ SUCCESS: 画像形式={img.format}, サイズ={img.size}")
                logging.info(f"画像形式={img.format}, サイズ={img.size}")
                img.load()  # 強制ロード
                return img
            except (UnidentifiedImageError, OSError) as e:
                print(f"❌ ERROR: 画像解析失敗（形式不明）: {type(e).__name__}: {e}")
                logging.error(f"画像解析失敗: {type(e).__name__}: {e}, url={url}")
                return None
            except Exception as e:
                print(f"⚠️ ERROR: 画像読み込みエラー: {type(e).__name__}: {e}, url={url}")
                logging.error(f"画像読み込みエラー: {type(e).__name__}: {e}, url={url}")
                return None
        except requests.RequestException as e:
            print(f"⚠️ ERROR: CDN取得失敗: {type(e).__name__}: {e}, url={url}")
            logging.error(f"CDN取得失敗: {type(e).__name__}: {e}, url={url}")
            continue

    if client and did_safe:
        try:
            print(f"🦊 Blob APIリクエスト開始: CID={cid}")
            logging.debug(f"Blob APIリクエスト開始: CID={cid}")
            blob = client.com.atproto.repo.get_blob(cid=cid, did=did_safe)
            print(f"✅ SUCCESS: Blob API取得成功: size={len(blob.data)} bytes")
            logging.debug(f"Blob API取得成功: size={len(blob.data)}")
            img_data = BytesIO(blob.data)
            try:
                img = Image.open(img_data)
                print(f"✅ SUCCESS: Blob画像形式={img.format}, サイズ={img.size}")
                logging.info(f"Blob画像形式={img.format}, サイズ={img.size}")
                img.load()  # 強制ロード
                return img
            except (UnidentifiedImageError, OSError) as e:
                print(f"❌ ERROR: Blob画像解析失敗（形式不明）: {type(e).__name__}: {e}")
                logging.error(f"Blob画像解析失敗: {type(e).__name__}: {e}")
                return None
            except Exception as e:
                print(f"⚠️ ERROR: Blob画像読み込みエラー: {type(e).__name__}: {e}")
                logging.error(f"Blob画像読み込みエラー: {type(e).__name__}: {e}")
                return None
        except Exception as e:
            print(f"⚠️ ERROR: Blob APIエラー: {type(e).__name__}: {e}")
            logging.error(f"Blob APIエラー: {type(e).__name__}: {e}")
            return None

    print("❌ ERROR: 画像取得失敗")
    logging.error("画像取得失敗")
    return None

def process_image(image_data, text="", client=None, post=None):
    if not hasattr(image_data, 'image') or not hasattr(image_data.image, 'ref'):
        print("❌ ERROR: 画像データ構造異常")
        logging.debug("画像データ構造異常")
        return False

    cid = extract_valid_cid(image_data.image.ref)
    if not cid:
        return False

    try:
        author_did = post.post.author.did if post and hasattr(post, 'post') else None
        img = download_image_from_blob(cid, client, did=author_did)
        if img is None:
            print("🦝 スキップ: 画像取得失敗")
            logging.warning("スキップ: 画像取得失敗（ログは上記）")
            return False

        img = img.resize((64, 64))
        colors = img.getdata()
        color_counts = Counter(colors)
        top_colors = color_counts.most_common(5)

        fluffy_count = 0
        for color in top_colors:
            r, g, b = color[0][:3]
            if is_fluffy_color(r, g, b):
                fluffy_count += 1

        skin_ratio = check_skin_ratio(image_data, client=client)
        if skin_ratio > 0.2:
            print("🦝 スキップ: 肌色比率高")
            logging.warning(f"スキップ: 肌色比率高: {skin_ratio:.2%}")
            return False

        check_text = text.lower()
        try:
            if any(word in check_text for word in globals()["HIGH_RISK_WORDS"]):
                if skin_ratio < 0.2 and fluffy_count >= 2:
                    print("🎉 SUCCESS: 高リスクだが条件OK")
                    logging.info("高リスクだが条件OK")
                    return True
                else:
                    print("🦝 スキップ: 高リスク＋条件NG")
                    logging.warning("スキップ: 高リスク＋条件NG")
                    return False
        except KeyError:
            logging.error("⚠️⚖️ HIGH_RISK_WORDS未定義。処理をスキップ")
            print("🦝 スキップ: HIGH_RISK_WORDS未定義")
            return False

        if fluffy_count >= 2:
            print("🎉 SUCCESS: ふわもこ色検出！")
            logging.info("ふわもこ色検出")
            return True
        else:
            print("🦝 スキップ: 色条件不足")
            logging.warning("スキップ: 色条件不足")
            return False
    except Exception as e:
        print(f"⚠️ ERROR: 画像処理エラー: {type(e).__name__}: {e}")
        logging.error(f"画像処理エラー: {type(e).__name__}: {e}")
        return False

def is_quoted_repost(post):
    try:
        actual_post = post.post if hasattr(post, 'post') else post
        record = getattr(actual_post, 'record', None)
        if record and hasattr(record, 'embed') and record.embed:
            embed = record.embed
            print(f"🦋 DEBUG: 引用リポストチェック: {embed}")
            logging.debug(f"引用リポストチェック: {embed}")
            if hasattr(embed, 'record') and embed.record:
                print("🦝 引用リポスト検出（record）")
                logging.debug("引用リポスト検出（record）")
                return True
            elif hasattr(embed, 'record') and hasattr(embed.record, 'record') and embed.record.record:
                print("🦝 引用リポスト検出（recordWithMedia）")
                logging.debug("引用リポスト検出（recordWithMedia）")
                return True
        return False
    except Exception as e:
        print(f"⚠️ ERROR: 引用リポストチェックエラー: {type(e).__name__}: {e}")
        logging.error(f"引用リポストチェックエラー: {type(e).__name__}: {e}")
        return False

def load_reposted_uris():
    REPOSTED_FILE = "reposted_uris.txt"
    if os.path.exists(REPOSTED_FILE):
        try:
            with open(REPOSTED_FILE, 'r', encoding='utf-8') as f:
                uris = set(line.strip() for line in f if line.strip())
                print(f"✅ SUCCESS: 再投稿URI読み込み: {len(uris)}件")
                logging.info(f"再投稿URI読み込み: {len(uris)}件")
                return uris
        except Exception as e:
            print(f"⚠️ ERROR: 再投稿URI読み込みエラー: {type(e).__name__}: {e}")
            logging.error(f"再投稿URI読み込みエラー: {type(e).__name__}: {e}")
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
        print(f"⚠️ ERROR: 言語判定エラー: {type(e).__name__}: {e}")
        logging.error(f"言語判定エラー: {type(e).__name__}: {e}")
        return "ja"

def is_priority_post(text):
    return "@mirinchuuu" in text.lower()

def is_reply_to_self(post):
    reply = getattr(post.record, "reply", None) if hasattr(post, 'record') else None
    if reply and hasattr(reply, 'parent') and hasattr(reply.parent, 'uri'):
        return reply.parent.uri == post.post.uri
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
        print(f"⚠️ ERROR: URI正規化エラー: {type(e).__name__}: {e}")
        logging.error(f"URI正規化エラー: {type(e).__name__}: {e}")
        return uri

def load_fuwamoko_uris():
    global fuwamoko_uris
    fuwamoko_uris.clear()
    if os.path.exists(FUWAMOKO_FILE):
        try:
            with open(FUWAMOKO_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
                print(f"📦 INFO: ふわもこ履歴サイズ: {len(content)} bytes")
                logging.info(f"ふわもこ履歴サイズ: {len(content)} bytes")
                if content.strip():
                    for line in content.splitlines():
                        if line.strip():
                            uri, timestamp = line.strip().split("|", 1)
                            fuwamoko_uris[normalize_uri(uri)] = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                print(f"📦 INFO: ふわもこURI読み込み: {len(fuwamoko_uris)}件")
                logging.info(f"ふわもこURI読み込み: {len(fuwamoko_uris)}件")
        except Exception as e:
            print(f"⚠️ ERROR: 履歴読み込みエラー: {type(e).__name__}: {e}")
            logging.error(f"履歴読み込みエラー: {type(e).__name__}: {e}")

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
                print(f"🦝 スキップ: 24時間以内: {normalized_uri.split('/')[-1]}")
                logging.debug(f"24時間以内スキップ: {normalized_uri}")
                return
            if isinstance(indexed_at, str):
                indexed_at = datetime.fromisoformat(indexed_at.replace("Z", "+00:00"))
            with open(FUWAMOKO_FILE, 'a', encoding='utf-8') as f:
                f.write(f"{normalized_uri}|{indexed_at.isoformat()}\n")
            fuwamoko_uris[normalized_uri] = indexed_at
            print(f"💾 SUCCESS: 履歴保存: {normalized_uri.split('/')[-1]}")
            logging.info(f"履歴保存: {normalized_uri}")
            load_fuwamoko_uris()
    except filelock.Timeout:
        print(f"⚠️ ERROR: ファイルロックタイムアウト: {FUWAMOKO_LOCK}")
        logging.error(f"ファイルロックタイムアウト: {FUWAMOKO_LOCK}")
    except Exception as e:
        print(f"⚠️ ERROR: 履歴保存エラー: {type(e).__name__}: {e}")
        logging.error(f"履歴保存エラー: {type(e).__name__}: {e}")

def load_session_string():
    try:
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE, 'r', encoding='utf-8') as f:
                return f.read().strip()
        return None
    except Exception as e:
        print(f"⚠️ ERROR: セッション読み込みエラー: {type(e).__name__}: {e}")
        logging.error(f"セッション読み込みエラー: {type(e).__name__}: {e}")
        return None

def save_session_string(session_str):
    try:
        with open(SESSION_FILE, 'w', encoding='utf-8') as f:
            f.write(session_str)
    except Exception as e:
        print(f"⚠️ ERROR: セッション保存エラー: {type(e).__name__}: {e}")
        logging.error(f"セッション保存エラー: {type(e).__name__}: {e}")

def has_image(post):
    try:
        actual_post = post.post if hasattr(post, 'post') else post
        if not hasattr(actual_post, 'record') or not hasattr(actual_post.record, 'embed'):
            return False
        embed = actual_post.record.embed
        return (
            (hasattr(embed, 'images') and embed.images) or
            (hasattr(embed, 'record') and hasattr(embed.record, 'embed') and hasattr(embed.record.embed, 'images') and embed.record.embed.images) or
            (getattr(embed, '$type', '') == 'app.bsky.embed.recordWithMedia' and hasattr(embed, 'media') and hasattr(embed.media, 'images') and embed.media.images)
        )
    except Exception as e:
        print(f"⚠️ ERROR: 画像チェックエラー: {type(e).__name__}: {e}")
        logging.error(f"画像チェックエラー: {type(e).__name__}: {e}")
        return False

def process_post(post_data, client, fuwamoko_uris, reposted_uris):
    try:
        actual_post = post_data.post if hasattr(post_data, 'post') else post_data
        uri = str(actual_post.uri)
        post_id = uri.split('/')[-1]
        text = getattr(actual_post.record, 'text', "") if hasattr(actual_post.record, 'text') else ""

        is_reply = hasattr(actual_post.record, "reply") and actual_post.record.reply is not None
        if is_reply and not (is_priority_post(text) or is_reply_to_self(post_data)):
            print(f"🦝 スキップ: リプライ（非@mir/非自己）: {text[:20]}")
            logging.debug(f"リプライスキップ: {post_id}")
            return False

        logging.info(f"🦓 POST処理開始: {post_id} by @{actual_post.author.handle}")
        if normalize_uri(uri) in fuwamoko_uris:
            print(f"🦝 スキップ: 既存投稿: {post_id}")
            logging.debug(f"スキップ: 既存投稿: {post_id}")
            return False
        if actual_post.author.handle == HANDLE:
            print(f"🦝 スキップ: 自分の投稿: {post_id}")
            logging.debug(f"スキップ: 自分の投稿: {post_id}")
            return False
        if is_quoted_repost(post_data):
            print(f"🦝 スキップ: 引用リポスト: {post_id}")
            logging.debug(f"スキップ: 引用リポスト: {post_id}")
            return False
        if post_id in reposted_uris:
            print(f"🦝 スキップ: 再投稿: {post_id}")
            logging.debug(f"スキップ: 再投稿: {post_id}")
            return False

        author = actual_post.author.handle
        indexed_at = actual_post.indexed_at

        if not has_image(post_data):
            print(f"🦝 スキップ: 画像なし: {post_id}")
            logging.debug(f"スキップ: 画像なし: {post_id}")
            return False

        image_data_list = []
        embed = getattr(actual_post.record, 'embed', None)
        if embed:
            if hasattr(embed, 'images') and embed.images:
                image_data_list.extend(embed.images)
            elif hasattr(embed, 'record') and hasattr(embed.record, 'embed') and hasattr(embed.record.embed, 'images'):
                image_data_list.extend(embed.record.embed.images)
            elif getattr(embed, '$type', '') == 'app -----------------------------------------------------------------------------------.bsky.embed.recordWithMedia' and hasattr(embed, 'media') and hasattr(embed.media, 'images'):
                image_data_list.extend(embed.media.images)

        if not is_mutual_follow(client, author):
            print(f"🦝 スキップ: 非相互フォロー: @{author}")
            logging.debug(f"スキップ: 非相互フォロー: {author}")
            return False

        for i, image_data in enumerate(image_data_list):
            try:
                print(f"🦓 画像処理開始: {i+1}/{len(image_data_list)}: {post_id}")
                logging.debug(f"画像処理開始: {i+1}/{len(image_data_list)}: {post_id}")
                if process_image(image_data, text, client=client, post=post_data):
                    if random.random() >= 0.5:
                        print(f"🦝 スキップ: ランダム（50%）: {post_id}")
                        logging.debug(f"スキップ: ランダム: {post_id}")
                        save_fuwamoko_uri(uri, indexed_at)
                        return False
                    lang = detect_language(client, author)
                    reply_text = open_calm_reply("", text, lang=lang)
                    if not reply_text:
                        print(f"🦝 スキップ: 返信生成失敗: {post_id}")
                        logging.debug(f"スキップ: 返信生成失敗: {post_id}")
                        save_fuwamoko_uri(uri, indexed_at)
                        return False
                    reply_ref = models.AppBskyFeedPost.ReplyRef(
                        root=models.AppBskyFeedPost.StrongRef(uri=uri, cid=actual_post.cid),
                        parent=models.AppBskyFeedPost.StrongRef(uri=uri, cid=actual_post.cid)
                    )
                    print(f"🦗 返信送信: @{author} - {reply_text}")
                    logging.debug(f"返信送信: {post_id} - @{author}: {reply_text}")
                    client.send_post(text=reply_text, reply_to=reply_ref)
                    save_fuwamoko_uri(uri, indexed_at)
                    print(f"✅ SUCCESS: 返信成功: @{author}")
                    logging.info(f"返信成功: @{author}")
                    return True
                    print(f"🦝 スキップ: ふわもこ画像でない: {post_id} (画像 {i+1})")
                        logging.debug(f"スキップ: ふわもこ画像でない: {post_id} (画像 {i+1})")
                    return False
                except Exception as e:
                    print(f"⚠�️ ERROR: 画像処理エラー: {type(e).__name__}: {e}")
                    logging.error(f"画像処理エラー: {type(e).__name__}: {e}")
                    return False

            except Exception as e:
                print(f"⚠️ ERROR: {画像処理エラー: {type(e).__name__}: {e}")
                logging.error(f"画像処理エラー: {type(e).__name__}: {e}")
                return False

def run_once():
    try::
        client = = Client()
        session_str = load_session_string()
        if session_str:
            client.login(session_string=session_str)
            print(f"🚀✩ START: ふわもこBot起動（セッション再利用）")
            logging.info("Bot起動: セッション再利用")
        else:
            client.login(HANDLE, APP_PASSWORD)
            session_str = client.export_session_string()
            save_session_string(session_str)
            print(f"🚀✩ START: ふわもこBot起動（新規セッション）")
            logging.info("Bot起動: 新規セッション")

        print(f"🦋 DEBUG: Bot HANDLE={HANDLE}")
        logging.debug(f"Bot HANDLE={HANDLE}")
        load_fuwamoko_uris()
        reposted_uris = load_reposted_uris()

        timeline = client.get_timeline(limit=50)
        feed = timeline.feed
        for post in sorted(feed, key=lambda x: x.post.indexed_at, reverse=True):
            try:
                thread_response = client.get_post_thread(uri=str(post.post.uri), depth=1)
                process_post(thread_response.thread, client, fuwamoko_uris, reposted_uris)
            except Exception as e:
                print(f"⚠️ ERROR: スレッド取得エラー: {type(e).__name__}: {e} (URI: {post.post.uri})")
                logging.error(f"スレッド取得エラー: {type(e).__name__}: {e} (URI: {post.post.uri})")
            time.sleep(1.0)
    except Exception as e:
        print(f"⚠️ ERROR: Bot実行エラー: {type(e).__name__}: {e}")
        logging.error(f"Bot実行エラー: {type(e).__name__}: {e}")

if __name__ == "__main__":
    load_dotenv()
    run_once()