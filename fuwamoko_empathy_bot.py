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
from copy import deepcopy
import json

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


# 🔽 テンプレ定義
LOCK_TEMPLATES = True
ORIGINAL_TEMPLATES = {
    "NORMAL_TEMPLATES_JP": [
        "うんうん、かわいいね！癒されたよ🐾💖",
        "よかったね〜！ふわふわだね🌸🧸",
        "えへっ、モフモフで癒しMAX！💞",
        "うわっ！可愛すぎるよ🐾🌷",
        "ふわふわだね、元気出た！💫🧸"
    ],
    "SHONBORI_TEMPLATES_JP": [
        "そっか…ぎゅーってしてあげるね🐾💕",
        "元気出してね、ふわもこパワー送るよ！🧸✨",
        "つらいときこそ、ふわふわに包まれて…🐰☁️",
        "無理しないでね、そっと寄り添うよ🧸🌸"
    ],
    "MOGUMOGU_TEMPLATES_JP": [
        "うーん…これは癒しより美味しそう？🐾💭",
        "もぐもぐしてるけど…ふわもこじゃないかな？🤔",
        "みりんてゃ、お腹空いてきちゃった…食レポ？🍽️💬"
    ],
    "NORMAL_TEMPLATES_EN": [
        "Wow, so cute! Feels good~ 🐾💖",
        "Nice! So fluffy~ 🌸🧸",
        "Great! Healing vibes! 💞",
        "Amazing! Thanks for the fluff! 🐾🌷"
    ],
    "MOGUMOGU_TEMPLATES_EN": [
        "Hmmm... looks tasty, but maybe not so fluffy? 🐾💭",
        "So yummy-looking... but is this a snack or a friend? 🤔🍽️",
        "This might be food, not a fluffy cutie... 🍽️💭",
        "Adorable! But maybe not a fluffy buddy? 🐑💬"
    ],
    "COSMETICS_TEMPLATES_JP": {
        "リップ": ["このリップ可愛い〜💄💖", "色味が素敵すぎてうっとりしちゃう💋"],
        "香水": ["この香り、絶対ふわもこだよね🌸", "いい匂い〜！💕"],
        "ネイル": ["そのネイル、キラキラしてて最高💅✨", "ふわもこカラーで素敵〜💖"]
    },
    "COSMETICS_TEMPLATES_EN": {
        "lip": ["That lipstick is so cute~ 💄💖", "The color is dreamy, I’m in love 💋"],
        "perfume": ["I bet that perfume smells fluffy and sweet 🌸", "I can almost smell it~ so lovely! 🌼"],
        "nail": ["That nail art is sparkly and perfect 💅✨", "Fluffy colors make it so pretty 💖"]
    },
    "CHARACTER_TEMPLATES_JP": {
        "アニメ": ["アニメキャラがモフモフ！💕", "まるで夢の世界の住人🌟"],
        "一次創作": ["オリキャラ尊い…🥺✨", "この子だけの世界観があるね💖"],
        "fanart": ["この解釈、天才すぎる…！🙌", "原作愛が伝わってくるよ✨"]
    },
    "CHARACTER_TEMPLATES_EN": {
        "anime": ["Such a fluffy anime character! 💕", "They look like someone from a dream world~ 🌟"],
        "oc": ["Your OC is precious... 🥺✨", "They have such a unique vibe, I love it! 💖"],
        "fanart": ["Amazing interpretation! You're a genius 🙌", "I can feel your love for the original work ✨"]
    }
}

# 🔽 グローバル辞書初期化
try:
    _ = globals()["HIGH_RISK_WORDS"]
except KeyError:
    logging.error("⚠️ HIGH_RISK_WORDSが未定義。デフォルトを注入します。")
    globals()["HIGH_RISK_WORDS"] = [
        "もちもち", "ぷにぷに", "ぷよぷよ", "やわらかい", "むにゅむにゅ", "エロ", "えっち",
        "nude", "nsfw", "naked", "lewd", "18+", "sex", "uncensored"
    ]

try:
    _ = globals()["EMOTION_TAGS"]
except KeyError:
    logging.error("⚠️ EMOTION_TAGSが未定義。デフォルトを注入します。")
    globals()["EMOTION_TAGS"] = {
        "fuwamoko": ["ふわふわ", "もこもこ", "もふもふ", "fluffy", "fluff", "fluffball", "ふわもこ",
                     "ぽよぽよ", "やわやわ", "きゅるきゅる", "ぽふぽふ", "ふわもふ", "ぽこぽこ"],
        "neutral": ["かわいい", "cute", "adorable", "愛しい"],
        "shonbori": ["しょんぼり", "つらい", "かなしい", "さびしい", "疲れた", "へこんだ", "泣きそう"],
        "food": ["肉", "ご飯", "飯", "ランチ", "ディナー", "モーニング", "ごはん",
                 "おいしい", "うまい", "いただきます", "たべた", "ごちそう", "ご馳走",
                 "まぐろ", "刺身", "チーズ", "スナック", "yummy", "delicious", "スープ",
                 "味噌汁", "カルボナーラ", "鍋", "麺", "パン", "トースト",
                 "カフェ", "ジュース", "ミルク", "ドリンク", "おやつ", "食事", "朝食", "夕食", "昼食",
                 "酒", "アルコール", "ビール", "ワイン", "酎ハイ", "カクテル", "ハイボール", "梅酒"],
        "safe_cosmetics": ["コスメ", "メイク", "リップ", "香水", "スキンケア", "ネイル", "爪", "マニキュア",
                          "cosmetics", "makeup", "perfume", "nail", "lip", "lipstick", "lip gloss", "lip balm",
                          "fragrance", "scent", "nail art", "manicure", "nails"]
    }

try:
    _ = globals()["SAFE_CHARACTER"]
except KeyError:
    logging.error("⚠️ SAFE_CHARACTERが未定義。デフォルトを注入します。")
    globals()["SAFE_CHARACTER"] = {
        "アニメ": ["アニメ", "漫画", "マンガ", "イラスト", "anime", "illustration", "drawing", "anime art", "manga", "fanart"],
        "一次創作": ["一次創作", "オリキャラ", "オリジナル", "創作", "oc", "original character", "my oc"],
        "fanart": ["ファンアート", "FA", "fanart", "fan art", "fandom art"]
    }

try:
    _ = globals()["GENERAL_TAGS"]
except KeyError:
    logging.error("⚠️ GENERAL_TAGSが未定義。デフォルトを注入します。")
    globals()["GENERAL_TAGS"] = ["キャラ", "推し", "art", "drawing"]

# テンプレ監査ログ
TEMPLATE_AUDIT_LOG = "template_audit_log.txt"

def audit_templates_changes(old, new):
    try:
        if old != new:
            with open(TEMPLATE_AUDIT_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "before": old,
                    "after": new
                }, ensure_ascii=False) + "\n")
            logging.warning("⚠️ テンプレ変更検出")
    except Exception as e:
        logging.error(f"⚠️ テンプレ監査エラー: {type(e).__name__}: {e}")

def check_template_integrity(templates):
    if not LOCK_TEMPLATES:
        logging.warning("⚠️ LOCK_TEMPLATES無効、改変リスク")
        return False
    for key in ORIGINAL_TEMPLATES:
        if templates.get(key) != ORIGINAL_TEMPLATES[key]:
            logging.error(f"⚠️ {key} 改変検出、復元推奨")
            return False
    return True

def auto_revert_templates(templates):
    if LOCK_TEMPLATES:
        for key in ORIGINAL_TEMPLATES:
            templates[key] = deepcopy(ORIGINAL_TEMPLATES[key])
        logging.info("✅ テンプレ復元完了")
        return templates
    return templates

def is_fluffy_color(r, g, b):
    logging.debug(f"色判定: RGB=({r}, {g}, {b})")
    if r > 230 and g > 230 and b > 230:  # 白系
        logging.debug("白系検出")
        return True
    if r > 220 and g < 100 and b > 180:  # ピンク系
        logging.debug("ピンク系検出")
        return True
    if r > 240 and g > 230 and b > 180:  # クリーム色系
        logging.debug("クリーム色系検出")
        return True
    if r > 220 and b > 220 and abs(r - b) < 30 and g > 200:  # パステルパープル
        logging.debug("パステルパープル検出")
        return True
    hsv = cv2.cvtColor(np.array([[[r, g, b]]], dtype=np.uint8), cv2.COLOR_RGB2HSV)[0][0]
    h, s, v = hsv
    logging.debug(f"HSV=({h}, {s}, {v})")
    if 200 <= h <= 300 and s < 50 and v > 200:  # パステル系（紫～ピンク）
        logging.debug("パステル系検出")
        return True
    if 200 <= h <= 250 and s < 100 and v > 150:  # 夜空パステル紫
        logging.debug("夜空パステル紫検出")
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
        r"(?:投稿|ユーザー|例文|擬音語|マスクット|マスケット|フォーラム|返事|会話|共感)",
        r"(?:癒し系のふわもこマスコット|投稿内容に対して)",
        r"[■#]{2,}",
        r"!{5,}", r"\?{5,}", r"[!？]{5,}",
        r"(?:(ふわ|もこ|もち|ぽこ)\1{2,})",  # 同一単語の3回以上繰り返しNG
        r"[♪~]{2,}",  # 記号連鎖
        r"#\S+#\S+",  # ハッシュタグ連鎖
    ]

    templates = deepcopy(ORIGINAL_TEMPLATES)
    if not check_template_integrity(templates):
        templates = auto_revert_templates(templates)
    audit_templates_changes(ORIGINAL_TEMPLATES, templates)

    NORMAL_TEMPLATES_JP = templates["NORMAL_TEMPLATES_JP"]
    SHONBORI_TEMPLATES_JP = templates["SHONBORI_TEMPLATES_JP"]
    MOGUMOGU_TEMPLATES_JP = templates["MOGUMOGU_TEMPLATES_JP"]
    NORMAL_TEMPLATES_EN = templates["NORMAL_TEMPLATES_EN"]
    MOGUMOGU_TEMPLATES_EN = templates["MOGUMOGU_TEMPLATES_EN"]
    COSMETICS_TEMPLATES_JP = templates["COSMETICS_TEMPLATES_JP"]
    COSMETICS_TEMPLATES_EN = templates["COSMETICS_TEMPLATES_EN"]
    CHARACTER_TEMPLATES_JP = templates["CHARACTER_TEMPLATES_JP"]
    CHARACTER_TEMPLATES_EN = templates["CHARACTER_TEMPLATES_EN"]

    detected_tags = []
    for tag, words in globals()["EMOTION_TAGS"].items():
        if any(word in text.lower() for word in words):
            detected_tags.append(tag)

    if "food" in detected_tags or any(word.lower() in text.lower() for word in NG_WORDS):
        logging.debug(f"NGワード/食事検出: {text[:40]}")
        return random.choice(MOGUMOGU_TEMPLATES_JP) if lang == "ja" else random.choice(MOGUMOGU_TEMPLATES_EN)
    elif "shonbori" in detected_tags:
        return random.choice(SHONBORI_TEMPLATES_JP) if lang == "ja" else random.choice(NORMAL_TEMPLATES_EN)
    elif "safe_cosmetics" in detected_tags:
        if lang == "ja":
            for cosmetic, templates in COSMETICS_TEMPLATES_JP.items():
                if cosmetic in text.lower():
                    return random.choice(templates)
        else:
            for cosmetic, templates in COSMETICS_TEMPLATES_EN.items():
                if any(word in text.lower() for word in globals()["EMOTION_TAGS"]["safe_cosmetics"]):
                    return random.choice(templates)
    elif any(tag in detected_tags for tag in globals()["SAFE_CHARACTER"]):
        if lang == "ja":
            for char_type, templates in CHARACTER_TEMPLATES_JP.items():
                if any(word in text.lower() for word in globals()["SAFE_CHARACTER"][char_type]):
                    return random.choice(templates)
        else:
            for char_type, templates in CHARACTER_TEMPLATES_EN.items():
                if any(word in text.lower() for word in globals()["SAFE_CHARACTER"][char_type]):
                    return random.choice(templates)
    elif any(word in text.lower() for word in globals()["GENERAL_TAGS"]):
        return random.choice(NORMAL_TEMPLATES_JP) if lang == "ja" else random.choice(NORMAL_TEMPLATES_EN)

    if not text.strip():
        text = "ふわふわな動物の画像だよ〜🌸"

    prompt = (
        "あなたは癒し系で可愛いマスコットです。\n"
        "以下の投稿を読んで、20〜30文字以内のふんわり優しい返信を1つ作ってください。\n"
        "絵文字は2〜3個、語尾は「〜ね！」「〜だよ！」など親しみやすくしてください。\n"
        "ハッシュタグ、記号の連続（♪〜）、単語の過剰な繰り返し（ふわふわふわ）は禁止です。\n"
        "自然で可愛い雰囲気にしてください。\n"
        "例:\n"
        "- わぁ〜もふもふの子に会えたの？🧸💕\n"
        "- 今日もふわふわ癒されるね〜🌙✨\n"
        "- ふわもこで癒される〜♡💖\n"
        "- そんな表情、かわいすぎるよ〜🐾🌼\n"
        "投稿: {text.strip()[:150]}\n"
        "返信: ###\n"
    )

    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=150).to(model.device)
    try:
    outputs = model.generate(
        **inputs,
        max_new_tokens=50,  # 余裕持たせる
        pad_token_id=tokenizer.pad_token_id,
        do_sample=True,
        temperature=0.7,  # 安定性重視
        top_k=40,
        top_p=0.9,
        no_repeat_ngram_size=3,
        stopping_criteria=[lambda ids, scores:
        "###" in tokenizer.decode(ids[0],
        skip_special_tokens=True)]
    )
        reply = tokenizer.decode(outputs[0], skip_special_tokens=True).strip()
        reply = re.sub(r'^.*?###\s*', '', reply, flags=re.DOTALL).strip()
        reply = re.sub(r'[■\s]+|(ユーザー|投稿|例文|擬音語|マスクット|マスケット|.*?:.*?[:;]|\#.*|[。！？]*)$', '', reply).strip()
        logging.debug(f"🧪 生出力: {reply}")

        # デバッグログ強化
        if len(reply) < 15 or len(reply) > 35:
            logging.warning(f"⏭️ SKIP: 長さ不適切: len={len(reply)}, テキスト: {reply[:60]}")
            return random.choice(NORMAL_TEMPLATES_JP) if lang == "ja" else random.choice(NORMAL_TEMPLATES_EN)
        
        for bad in NG_PHRASES:
            if re.search(bad, reply.lower()):
                logging.warning(f"⏭️ SKIP: NGフレーズ検出: {bad}, テキスト: {reply[:60]}")
                return random.choice(NORMAL_TEMPLATES_JP) if lang == "ja" else random.choice(NORMAL_TEMPLATES_EN)

        emoji_count = len(re.findall(r'[😺🐾🧸🌸🌟💕💖✨☁️🌷🐰]', reply))
        if emoji_count < 2 or emoji_count > 3:
            logging.warning(f"⏭️ SKIP: 絵文字数不適切: count={emoji_count}, テキスト: {reply[:60]}")
            return random.choice(NORMAL_TEMPLATES_JP) if lang == "ja" else random.choice(NORMAL_TEMPLATES_EN)

        logging.info(f"🦊 AI生成成功: {reply}")
        return reply
    except Exception as e:
        logging.error(f"❌ AI生成エラー: {type(e).__name__}: {e}")
        return random.choice(NORMAL_TEMPLATES_JP) if lang == "ja" else random.choice(NORMAL_TEMPLATES_EN)

def extract_valid_cid(ref):
    try:
        cid_candidate = str(ref.link) if hasattr(ref, 'link') else str(ref)
        if re.match(r'^baf[a-z0-9]{40,60}$', cid_candidate):
            return cid_candidate
        logging.error(f"❌ 無効なCID: {cid_candidate}")
        return None
    except Exception as e:
        logging.error(f"❌ CID抽出エラー: {type(e).__name__}: {e}")
        return None

def check_skin_ratio(img_pil_obj):
    try:
        if img_pil_obj is None:
            logging.debug("画像データ無効 (PIL ImageオブジェクトがNone)")
            return 0.0

        img_pil_obj = img_pil_obj.convert("RGB")
        img_np = cv2.cvtColor(np.array(img_pil_obj), cv2.COLOR_RGB2BGR)
        if img_np is None or img_np.size == 0:
            logging.error("❌ 画像データ無効")
            return 0.0

        hsv_img = cv2.cvtColor(img_np, cv2.COLOR_BGR2HSV)
        lower = np.array([5, 20, 70], dtype=np.uint8)
        upper = np.array([25, 180, 255], dtype=np.uint8)
        mask = cv2.inRange(hsv_img, lower, upper)
        skin_colors = img_np[mask > 0]
        if skin_colors.size > 0:
            avg_color = np.mean(skin_colors, axis=0)
            logging.debug(f"平均肌色: BGR={avg_color}")
        skin_area = np.sum(mask > 0)
        total_area = img_np.shape[0] * img_np.shape[1]
        skin_ratio = skin_area / total_area if total_area > 0 else 0.0
        logging.debug(f"肌色比率: {skin_ratio:.2%}")
        return skin_ratio
    except Exception as e:
        logging.error(f"❌ 肌色解析エラー: {type(e).__name__}: {e}")
        return 0.0

def is_mutual_follow(client, handle):
    try:
        their_followers = client.get_followers(actor=handle, limit=100).followers
        their_followers = {f.handle for f in their_followers}
        my_followers = client.get_followers(actor=HANDLE, limit=100).followers
        my_followers = {f.handle for f in my_followers}
        return handle in my_followers and HANDLE in their_followers
    except Exception as e:
        logging.error(f"❌ 相互フォロー判定エラー: {type(e).__name__}: {e}")
        return False

def download_image_from_blob(cid, client, did=None):
    if not cid or not re.match(r'^baf[a-z0-9]{40,60}$', cid):
        logging.error(f"❌ 無効なCID: {cid}")
        return None

    if client and did:
        try:
            logging.debug(f"🦊 Blob APIリクエスト開始: CID={cid}, DID={did}")
            blob = client.com.atproto.repo.get_blob(cid=cid, did=did)
            logging.debug(f"Blob API取得成功: size={len(blob.data)} bytes")
            img_data = BytesIO(blob.data)
            try:
                img = Image.open(img_data)
                logging.info(f"🟢 Blob画像形式={img.format}, サイズ={img.size}")
                img.load()
                return img
            except (UnidentifiedImageError, OSError) as e:
                logging.error(f"❌ Blob画像解析失敗: {type(e).__name__}: {e}")
                return None
            except Exception as e:
                logging.error(f"❌ Blob画像読み込みエラー: {type(e).__name__}: {e}")
                return None
        except Exception as e:
            logging.error(f"❌ Blob APIエラー: {type(e).__name__}: {e}")

    did_safe = unquote(did) if did else None
    cdn_urls = [
        f"https://cdn.bsky.app/img/feed_thumbnail/plain/{quote(did_safe)}/{quote(cid)}@jpeg" if did_safe else None,
        f"https://cdn.bsky.app/img/feed_full/plain/{quote(did_safe)}/{quote(cid)}@jpeg" if did_safe else None
    ]
    headers = {"User-Agent": "Mozilla/5.0"}

    for url in [u for u in cdn_urls if u]:
        try:
            logging.debug(f"🦊 CDNリクエスト開始: CID={cid}, url={url}")
            response = requests.get(url, headers=headers, timeout=10, stream=True)
            response.raise_for_status()
            logging.debug(f"CDN取得成功: サイズ={len(response.content)} bytes")
            img_data = BytesIO(response.content)
            try:
                img = Image.open(img_data)
                logging.info(f"🟢 画像形式={img.format}, サイズ={img.size}")
                img.load()
                return img
            except (UnidentifiedImageError, OSError) as e:
                logging.error(f"❌ 画像解析失敗: {type(e).__name__}: {e}, url={url}")
                return None
            except Exception as e:
                logging.error(f"❌ 画像取得エラー: {type(e).__name__}: {e}, url={url}")
                return None
        except requests.RequestException as e:
            logging.error(f"❌ CDN取得失敗: {type(e).__name__}: {e}, url={url}")
            continue

    logging.error("❌ 画像取得失敗")
    return None

def process_image(image_data, text="", client=None, post=None):
    if not hasattr(image_data, 'image') or not hasattr(image_data.image, 'ref'):
        logging.debug("画像データ構造異常")
        return False

    cid = extract_valid_cid(image_data.image.ref)
    if not cid:
        return False

    try:
        author_did = post.post.author.did if post and hasattr(post, 'post') else None
        img = download_image_from_blob(cid, client, did=author_did)
        if img is None:
            logging.warning("⏭️ スキップ: 画像取得失敗（ログは上記）")
            return False

        resized_img = img.resize((64, 64))
        colors = resized_img.getdata()
        color_counts = Counter(colors)
        top_colors = color_counts.most_common(5)
        logging.debug(f"トップ5カラー: {[(c[0][:3], c[1]) for c in top_colors]}")

        fluffy_count = 0
        for color in top_colors:
            r, g, b = color[0][:3]
            if is_fluffy_color(r, g, b):
                fluffy_count += 1
        logging.debug(f"ふわもこ色カウント: {fluffy_count}")

        skin_ratio = check_skin_ratio(img)
        if skin_ratio > 0.4:
            logging.warning(f"⏭️ スキップ: 肌色比率高: {skin_ratio:.2%}")
            return False

        check_text = text.lower()
        try:
            if any(word in check_text for word in globals()["HIGH_RISK_WORDS"]):
                if skin_ratio < 0.4 and fluffy_count >= 2:
                    logging.info("🟢 高リスクだが条件OK")
                    return True
                else:
                    logging.warning("⏭️ スキップ: 高リスク＋条件NG")
                    return False
        except KeyError:
            logging.error("❌ HIGH_RISK_WORDS未定義。処理をスキップ")
            return False

        if fluffy_count >= 2:
            logging.info("🟢 ふわもこ色検出")
            return True
        else:
            logging.warning("⏭️ スキップ: 色条件不足")
            return False
    except Exception as e:
        logging.error(f"❌ 画像処理エラー: {type(e).__name__}: {e}")
        return False

def is_quoted_repost(post):
    try:
        actual_post = post.post if hasattr(post, 'post') else post
        record = getattr(actual_post, 'record', None)
        if record and hasattr(record, 'embed') and record.embed:
            embed = record.embed
            logging.debug(f"引用リポストチェック: {embed}")
            if hasattr(embed, 'record') and embed.record:
                logging.debug("引用リポスト検出（record）")
                return True
            elif hasattr(embed, 'record') and hasattr(embed.record, 'record') and embed.record.record:
                logging.debug("引用リポスト検出（recordWithMedia）")
                return True
        return False
    except Exception as e:
        logging.error(f"❌ 引用リポストチェックエラー: {type(e).__name__}: {e}")
        return False

def load_reposted_uris():
    REPOSTED_FILE = "reposted_uris.txt"
    if os.path.exists(REPOSTED_FILE):
        try:
            with open(REPOSTED_FILE, 'r', encoding='utf-8') as f:
                uris = set(line.strip() for line in f if line.strip())
                logging.info(f"🟢 再投稿URI読み込み: {len(uris)}件")
                return uris
        except Exception as e:
            logging.error(f"❌ 再投稿URI読み込みエラー: {type(e).__name__}: {e}")
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
        logging.error(f"❌ 言語判定エラー: {type(e).__name__}: {e}")
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
            normalized = f"at://{parts[2]}/{parts[3]}/{parts[4]}"
            logging.debug(f"🦊 URI正規化: {uri} -> {normalized}")
            return normalized
        logging.warning(f"⏭️ URI正規化失敗: 不正な形式: {uri}")
        return uri
    except Exception as e:
        logging.error(f"❌ URI正規化エラー: {type(e).__name__}: {e}")
        return uri

def validate_fuwamoko_file():
    if not os.path.exists(FUWAMOKO_FILE):
        logging.info("🟢 ふわもこ履歴ファイルが存在しません。新規作成します。")
        with open(FUWAMOKO_FILE, 'w', encoding='utf-8') as f:
            f.write("")
        return True
    try:
        with open(FUWAMOKO_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines:
                clean_line = line.strip()
                if not clean_line:
                    continue
                if not re.match(r'^at://[^|]+\|\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}(?:\d{3})?\+\d{2}:\d{2}$', clean_line):
                    logging.error(f"❌ 無効な履歴行: {repr(clean_line)}")
                    return False
        return True
    except Exception as e:
        logging.error(f"❌ 履歴ファイル検証エラー: {type(e).__name__}: {e}")
        return False

def repair_fuwamoko_file():
    temp_file = FUWAMOKO_FILE + ".tmp"
    valid_lines = []
    if os.path.exists(FUWAMOKO_FILE):
        try:
            with open(FUWAMOKO_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    clean_line = line.strip()
                    if not clean_line:
                        continue
                    if re.match(r'^at://[^|]+\|\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}(?:\d{3})?\+\d{2}:\d{2}$', clean_line):
                        valid_lines.append(line)
                    else:
                        logging.warning(f"⏭️ 破損行スキップ: {repr(clean_line)}")
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.writelines(valid_lines)
            os.replace(temp_file, FUWAMOKO_FILE)
            logging.info(f"🟢 履歴ファイル修復完了: {len(valid_lines)}件保持")
        except Exception as e:
            logging.error(f"❌ 履歴ファイル修復エラー: {type(e).__name__}: {e}")
            if os.path.exists(temp_file):
                os.remove(temp_file)
    else:
        with open(FUWAMOKO_FILE, 'w', encoding='utf-8') as f:
            f.write("")
        logging.info("🟢 新規履歴ファイル作成")

def load_fuwamoko_uris():
    global fuwamoko_uris
    fuwamoko_uris.clear()
    if not validate_fuwamoko_file():
        logging.warning("⚠️ 履歴ファイル破損。修復を試みます。")
        repair_fuwamoko_file()
    try:
        with open(FUWAMOKO_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
            logging.info(f"🟢 ふわもこ履歴サイズ: {len(content)} bytes")
            if content.strip():
                for line in content.splitlines():
                    if line.strip():
                        try:
                            uri, timestamp = line.strip().split("|", 1)
                            normalized_uri = normalize_uri(uri)
                            fuwamoko_uris[normalized_uri] = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                            logging.debug(f"🦊 履歴読み込み: {normalized_uri}")
                        except ValueError as e:
                            logging.warning(f"⏭️ 破損行スキップ: {repr(line.strip())}: {e}")
                            continue
            logging.info(f"🟢 ふわもこURI読み込み: {len(fuwamoko_uris)}件")
    except Exception as e:
        logging.error(f"❌ 履歴読み込みエラー: {type(e).__name__}: {e}")
        fuwamoko_uris.clear()

def save_fuwamoko_uri(uri, indexed_at):
    global fuwamoko_uris
    normalized_uri = normalize_uri(uri)
    lock = filelock.FileLock(FUWAMOKO_LOCK, timeout=5.0)
    try:
        with lock:
            logging.debug(f"🦊 ロック取得: {FUWAMOKO_LOCK}")
            if normalized_uri in fuwamoko_uris and (datetime.now(timezone.utc) - fuwamoko_uris[normalized_uri]).total_seconds() < 24 * 3600:
                logging.debug(f"⏭️ スキップ: 24時間以内: {normalized_uri}")
                return
            if isinstance(indexed_at, str):
                indexed_at = datetime.fromisoformat(indexed_at.replace("Z", "+00:00"))
            with open(FUWAMOKO_FILE, 'a', encoding='utf-8') as f:
                f.write(f"{normalized_uri}|{indexed_at.isoformat()}\n")
            fuwamoko_uris[normalized_uri] = indexed_at  # メモリ更新
            logging.info(f"🟢 履歴保存: {normalized_uri}")
            # ファイル確認
            with open(FUWAMOKO_FILE, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                last_line = lines[-1].strip() if lines else ""
                if last_line.startswith(normalized_uri):
                    logging.debug(f"🦊 履歴ファイル確認: 最後の行={last_line}")
                else:
                    logging.error(f"❌ 履歴保存失敗: 最後の行={last_line}")
            # 再読み込み
            load_fuwamoko_uris()  # ★追加
    except filelock.Timeout:
        logging.error(f"❌ ファイルロックタイムアウト: {FUWAMOKO_LOCK}")
    except Exception as e:
        logging.error(f"❌ 履歴保存エラー: {type(e).__name__}: {e}")

def load_session_string():
    try:
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE, 'r', encoding='utf-8') as f:
                return f.read().strip()
        return None
    except Exception as e:
        logging.error(f"❌ セッション読み込みエラー: {type(e).__name__}: {e}")
        return None

def save_session_string(session_str):
    try:
        with open(SESSION_FILE, 'w', encoding='utf-8') as f:
            f.write(session_str)
    except Exception as e:
        logging.error(f"❌ セッション保存エラー: {type(e).__name__}: {e}")

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
        logging.error(f"❌ 画像チェックエラー: {type(e).__name__}: {e}")
        return False

def process_post(post_data, client, fuwamoko_uris, reposted_uris):
    try:
        actual_post = post_data.post if hasattr(post_data, 'post') else post_data
        uri = str(actual_post.uri)
        post_id = uri.split('/')[-1]
        text = getattr(actual_post.record, 'text', '') if hasattr(actual_post.record, 'text') else ''

        is_reply = hasattr(actual_post.record, 'reply') and actual_post.record.reply is not None
        if is_reply and not (is_priority_post(text) or is_reply_to_self(post_data)):
            print(f"⏭️ スキップ: リプライ（非@mirinchuuu/非自己）: {text[:20]} ({post_id})")
            logging.debug(f"スキップ: リプライ: {post_id}")
            return False

        print(f"🦊 POST処理開始: @{actual_post.author.handle} ({post_id})")
        logging.info(f"🟢 POST処理開始: @{actual_post.author.handle} ({post_id})")
        normalized_uri = normalize_uri(uri)
        if normalized_uri in fuwamoko_uris:
            print(f"⏭️ スキップ: 既存投稿: {post_id}")
            logging.debug(f"スキップ: 既存投稿: {post_id}")
            return False
        if actual_post.author.handle == HANDLE:
            print(f"⏭️ スキップ: 自分の投稿: {post_id}")
            logging.debug(f"スキップ: 自分の投稿: {post_id}")
            return False
        if is_quoted_repost(post_data):
            print(f"⏭️ スキップ: 引用リポスト: {post_id}")
            logging.debug(f"スキップ: 引用リポスト: {post_id}")
            return False
        if post_id in reposted_uris:
            print(f"⏭️ スキップ: 再投稿済み: {post_id}")
            logging.debug(f"スキップ: 再投稿済み: {post_id}")
            return False

        author = actual_post.author.handle
        indexed_at = actual_post.indexed_at

        if not has_image(post_data):
            print(f"⏭️ スキップ: 画像なし: {post_id}")
            logging.debug(f"スキップ: 画像なし: {post_id}")
            return False

        image_data_list = []
        embed = getattr(actual_post.record, 'embed', None)
        if embed:
            if hasattr(embed, 'images') and embed.images:
                image_data_list.extend(embed.images)
            elif hasattr(embed, 'record') and hasattr(embed.record, 'embed') and hasattr(embed.record.embed, 'images'):
                image_data_list.extend(embed.record.embed.images)
            elif getattr(embed, '$type', '') == 'app.bsky.embed.recordWithMedia' and hasattr(embed, 'media') and hasattr(embed.media, 'images'):
                image_data_list.extend(embed.media.images)

        if not is_mutual_follow(client, author):
            print(f"⏭️ スキップ: 非相互フォロー: @{author} ({post_id})")
            logging.debug(f"スキップ: 非相互フォロー: @{author} ({post_id})")
            return False

        for i, image_data in enumerate(image_data_list):
            try:
                print(f"🦊 画像処理開始: {i+1}/{len(image_data_list)} ({post_id})")
                logging.debug(f"画像処理開始: {i+1}/{len(image_data_list)} ({post_id})")
                if process_image(image_data, text, client=client, post=post_data):
                    if random.random() > 0.5:
                        print(f"⏭️ スキップ: ランダム（50%）: {post_id}")
                        logging.debug(f"スキップ: ランダム: {post_id}")
                        save_fuwamoko_uri(uri, indexed_at)  # ランダムスキップでも保存
                        return False
                    lang = detect_language(client, author)
                    reply_text = open_calm_reply("", text, lang=lang)
                    if not reply_text:
                        print(f"⏭️ スキップ: 返信生成失敗: {post_id}")
                        logging.debug(f"スキップ: 返信生成失敗: {post_id}")
                        save_fuwamoko_uri(uri, indexed_at)  # 生成失敗でも保存
                        return False
                    root_ref = models.ComAtprotoRepoStrongRef.Main(
                        uri=uri,
                        cid=actual_post.cid
                    )
                    parent_ref = models.ComAtprotoRepoStrongRef.Main(
                        uri=uri,
                        cid=actual_post.cid
                    )
                    reply_ref = models.AppBskyFeedPost.ReplyRef(
                        root=root_ref,
                        parent=parent_ref
                    )
                    print(f"🦊 返信送信: @{author}: {reply_text} ({post_id})")
                    logging.debug(f"返信送信: @{author}: {reply_text} ({post_id})")
                    client.send_post(text=reply_text, reply_to=reply_ref)
                    save_fuwamoko_uri(uri, indexed_at)  # 返信成功で保存
                    print(f"✅ SUCCESS: 返信成功: @{author} ({post_id})")
                    logging.info(f"🟢 返信成功: @{author} ({post_id})")
                    return True
                else:
                    print(f"⏭️ スキップ: ふわもこ画像でない: {post_id} (画像 {i+1})")
                    logging.warning(f"⏭️ スキップ: ふわもこ画像でない: {post_id} (画像 {i+1})")
                    save_fuwamoko_uri(uri, indexed_at)  # ふわもこでない場合も保存
                    return False
            except Exception as e:
                print(f"❌ 画像処理エラー: {type(e).__name__}: {e} ({post_id}, uri={uri}, cid={actual_post.cid})")
                logging.error(f"❌ 画像処理エラー: {type(e).__name__}: {e} ({post_id}, uri={uri}, cid={actual_post.cid})")
                save_fuwamoko_uri(uri, indexed_at)  # エラーでも保存
                return False
    except Exception as e:
        print(f"❌ 投稿処理エラー: {type(e).__name__}: {e} ({post_id}, uri={uri})")
        logging.error(f"❌ 投稿処理エラー: {type(e).__name__}: {e} ({post_id}, uri={uri})")
        save_fuwamoko_uri(uri, indexed_at)  # エラーでも保存
        return False

def run_once():
    try:
        client = Client()
        session_str = load_session_string()
        if session_str:
            client.login(session_string=session_str)
            print(f"🚀✨ START: ふわもこBot起動（セッション再利用）")
            logging.info("🟢 Bot起動: セッション再利用")
        else:
            client.login(HANDLE, APP_PASSWORD)
            session_str = client.export_session_string()
            save_session_string(session_str)
            print(f"🚀✨ START: ふわもこBot起動（新規セッション）")
            logging.info("🟢 Bot起動: 新規セッション")

        print(f"🦊 INFO: Bot稼働中: {HANDLE}")
        logging.info(f"🟢 Bot稼働中: {HANDLE}")
        load_fuwamoko_uris()
        reposted_uris = load_reposted_uris()

        timeline = client.get_timeline(limit=50)
        feed = timeline.feed
        for post in sorted(feed, key=lambda x: x.post.indexed_at, reverse=True):
            try:
                thread_response = client.get_post_thread(uri=str(post.post.uri), depth=2)
                process_post(thread_response.thread, client, fuwamoko_uris, reposted_uris)
            except Exception as e:
                print(f"❌ スレッド取得エラー: {type(e).__name__}: {e} (URI: {post.post.uri})")
                logging.error(f"❌ スレッド取得エラー: {type(e).__name__}: {e} (URI: {post.post.uri})")
            time.sleep(1.0)
    except Exception as e:
        print(f"❌ Bot実行エラー: {type(e).__name__}: {e}")
        logging.error(f"❌ Bot実行エラー: {type(e).__name__}: {e}")

if __name__ == "__main__":
    try:
        load_dotenv()
        run_once()
    except Exception as e:
        logging.error(f"❌ Bot起動エラー: {type(e).__name__}: {e}")