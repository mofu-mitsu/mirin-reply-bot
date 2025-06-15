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

# 🔽 テンプレ保護（チャッピー憲章）
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
        "漫画": ["コマから飛び出してきたみたい！📖✨", "このタッチ、めちゃ好み…！💘"],
        "イラスト": ["線の優しさに癒される…🖋️🌼", "色づかいがほんと素敵💖"],
        "一次創作": ["オリキャラ尊い…🥺✨", "この子だけの世界観があるね💖"],
        "二次創作": ["この解釈、天才すぎる…！🙌", "原作愛が伝わってくるよ✨"]
    },
    "CHARACTER_TEMPLATES_EN": {
        "anime": ["That anime character looks so fluffy! 💕", "Like someone straight out of a dream world~ 🌟"],
        "manga": ["They look like they just stepped out of a manga panel! 📖✨", "I love the vibe of this linework! 💘"],
        "illustration": ["The softness in these lines is so comforting~ 🖋️🌼", "The colors are simply beautiful! 💖"],
        "oc": ["Your OC is precious… 🥺✨", "They have such a unique and magical world of their own 💖"],
        "fanart": ["Your interpretation is genius! 🙌", "I can feel your love for the original work ✨"]
    }
}

# 🔽 グローバル辞書初期化
try:
    _ = globals()["EMOTION_TAGS"]
except KeyError:
    logging.error("⚠️ EMOTION_TAGS未定義。デフォルトを注入します。")
    globals()["EMOTION_TAGS"] = {
        "fuwamoko": ["ふわふわ", "もこもこ", "もふもふ", "fluffy", "fluff", "fluffball", "ふわもこ",
                     "ぽよぽよ", "やわやわ", "きゅるきゅる", "ぽふぽふ", "ふわもふ", "雲"],
        "neutral": ["かわいい", "cute", "adorable", "愛しい"],
        "shonbori": ["しょんぼり", "つらい", "かなしい", "さびしい", "疲れた", "へこんだ", "泣きそう"],
        "food_ng": ["肉", "ご飯", "飯", "ランチ", "ディナー", "モーニング", "ごはん", "卵", "たまご", "おにぎり",
                    "おいしい", "うまい", "美味", "いただきます", "たべた", "食", "ごちそう", "ご馳走",
                    "まぐろ", "刺身", "チーズ", "スナック", "yummy", "delicious", "スープ",
                    "味噌汁", "カルボナーラ", "鍋", "麺", "パン", "トースト", "豆腐",
                    "カフェ", "ジュース", "ミルク", "ドリンク", "おやつ", "食事", "朝食", "夕食", "昼食"],
        "nsfw_ng": ["酒", "アルコール", "ビール", "ワイン", "酎ハイ", "カクテル", "ハイボール", "梅酒",
                    "soft core", "NSFW", "肌色", "下着", "肌見せ", "露出", "肌フェチ", "soft skin", "fetish",
                    "nude", "naked", "lewd", "18+", "sex", "uncensored",
                    "Hカップ", "吉原", "風俗", "ランジェリー", "おっぱい", "セクシー", "挑発", "谷間", "胸元", "乳", "水着姿", "エロ", "えちえち", "ぱい"]
    }

try:
    _ = globals()["SAFE_CHARACTER"]
except KeyError:
    logging.error("⚠️ SAFE_CHARACTER未定義。デフォルトを注入します。")
    globals()["SAFE_CHARACTER"] = {
        "アニメ": ["アニメ", "anime", "anime art", "アニメキャラ"],
        "漫画": ["漫画", "マンガ", "manga", "comic"],
        "イラスト": ["イラスト", "illustration", "drawing", "スケッチ", "art", "落書き"],
        "一次創作": ["一次創作", "オリキャラ", "オリジナル", "oc", "original character", "my oc"],
        "二次創作": ["二次創作", "fanart", "fan art", "FA", "fandom art", "原作キャラ", "原作再現", "推しキャラ"]
    }

try:
    _ = globals()["GENERAL_TAGS"]
except KeyError:
    logging.error("⚠️ GENERAL_TAGS未定義。デフォルトを注入します。")
    globals()["GENERAL_TAGS"] = ["キャラ", "推し"]

try:
    _ = globals()["HIGH_RISK_WORDS"]
except KeyError:
    logging.error("⚠️ HIGH_RISK_WORDS未定義。デフォルトを注入します。")
    globals()["HIGH_RISK_WORDS"] = ["もちもち", "ぷにぷに", "ぷよぷよ", "やわらかい", "むにゅむにゅ", "エロ", "えっち"]

# 優先順位
PRIORITY_ORDER = ["二次創作", "一次創作", "アニメ", "漫画", "イラスト"]

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
                }, ensure_ascii=False, indent=2) + "\n")
            logging.warning("⚠️ テンプレ変更検出")
    except Exception as e:
        logging.error(f"❌ テンプレ監査エラー: {type(e).__name__}: {e}")

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

fuwamoko_tone_map = [
    ("ありがとうございます", "ありがと🐰💓"),
    ("ありがとう", "ありがと♪"),
    ("ですね", "だね〜✨"),
    ("ですよ", "だよ♡"),
    ("です", "だよ♡"),
    ("ます", "するよ♪"),
    ("ました", "したよ〜💖"),
]

def apply_fuwamoko_tone(reply):
    for formal, soft in fuwamoko_tone_map:
        reply = reply.replace(formal, soft)
    reply = re.sub(r'(🐰💓)\.', r'\1', reply)  # 句点と絵文字の異常修正
    return reply

def is_fluffy_color(r, g, b, bright_colors):
    logging.debug(f"🧪 色判定: RGB=({r}, {g}, {b})")
    hsv = cv2.cvtColor(np.array([[[r, g, b]]], dtype=np.uint8), cv2.COLOR_RGB2HSV)[0][0]
    h, s, v = hsv
    logging.debug(f"HSV=({h}, {s}, {v})")

    # 食品色範囲（ハム/卵/おにぎり/豆腐、桃花除外）
    if ((150 <= r <= 200 and 150 <= g <= 200 and 150 <= b <= 200) or  # ハム/卵
        (220 <= r <= 250 and 220 <= g <= 250 and 210 <= b <= 230) or  # おにぎり
        (230 <= r <= 255 and 200 <= g <= 230 and 130 <= b <= 160) or  # 豆腐
        (r == 255 and g == 255 and b == 255)):                       # 純白
        logging.debug("食品色（ハム/卵/おにぎり/豆腐/純白）検出、ふわもことみなさない")
        return False

    # 白系（明るさv > 130、単色閾値10）
    if r > 180 and g > 180 and b > 180 and v > 130:
        if bright_colors and len(bright_colors) > 0:
            colors = np.array(bright_colors)
            if np.std(colors, axis=0).max() < 10:
                logging.debug("単色白系、ふわもことみなさない")
                return False
        logging.debug("白系検出（明るさOK、ピンク寄り含む）")
        return True

    # ピンク系（桃花優先）
    if (r > 200 and g < 170 and b > 170 and v > 130) or \
       (220 <= r <= 240 and 220 <= g <= 240 and 230 <= b <= 250):  # #232, 236, 247 対応
        logging.debug("ピンク系検出（桃花優先、明るさOK）")
        return True

    # クリーム色
    if r > 220 and g > 210 and b > 170 and v > 130:
        logging.debug("クリーム色検出（広め）")
        return True

    # パステルパープル
    if (r > 220 and g > 210 and b > 240 and abs(r - b) < 60 and v > 130) or \
       (220 <= h <= 300 and s < 50 and v > 130):  # #F6DAF6, #E9DAF9 対応
        logging.debug("パステルパープル検出（明るさOK）")
        return True

    # 白灰ピンク系
    if r > 200 and g > 180 and b > 200 and v > 130:
        logging.debug("ふわもこ白灰ピンク検出（桃花対応）")
        return True

    # 白灰系
    if 200 <= r <= 255 and 200 <= g <= 240 and 200 <= b <= 255 and abs(r - g) < 30 and abs(r - b) < 30 and v > 130:
        logging.debug("白灰ふわもこカラー（柔らか系）")
        return True

    if 200 <= h <= 300 and s < 80 and v > 130:
        logging.debug("パステル系紫～ピンク検出（明るさOK）")
        return True

    if 190 <= h <= 260 and s < 100 and v > 130:
        logging.debug("夜空パステル紫検出（広め、明るさOK）")
        return True

    return False

def clean_output(text):
    text = re.sub(r'[\r\n]+', ' ', text)
    text = re.sub(r'\s{2,}', ' ', text)
    text = re.sub(r'^(短く、ふわもこな返事をしてね。|.*→\s*|寒い〜\s*)', '', text)
    text = re.sub(r'^.*?((もふ|ふわ)[^。]*)$', r'\1', text, flags=re.DOTALL)
    text = re.sub(r'^もふもふであったまろ〜♡\s*', '', text)  # テンプレ削除
    text = re.sub(r'^[^。！？\n]{1,10}って癒されるよね〜\s*', '', text)  # テンプレ削除
    text = re.sub(r'[^\w\sぁ-んァ-ン一-龯。、！？!?♡（）「」♪〜ー…w笑]+', '', text)
    text = re.sub(r'([。、！？])\s*💖', r'\1💖', text)
    text = re.sub(r'[。、！？]{2,}', lambda m: m.group(0)[0], text)
    return text.strip()

def open_calm_reply(image_url, text="", context="ふわもこ共感", lang="ja"):
    NG_WORDS = globals()["EMOTION_TAGS"].get("nsfw_ng", [])
    NG_PHRASES = [
        r"(?:投稿|ユーザー|例文|マスクット|マスケット|フォーラム|返事|会話|共感)",
        r"(?:癒し系のふわもこマスコット|投稿内容に対して)",
        r"[■#]{2,}",
        r"!{5,}", r"\?{5,}", r"[!？]{5,}",
        r"(?:(ふわ|もこ|もち|ぽこ)\1{3,})",
        r"[♪~]{2,}",
        r"(#\w+){3,}",
        r"^[^\w\s]+$", r"(\w+\s*,){3,}", r"[\*:\.]{2,}"
    ]
    SEASONAL_WORDS_BLACKLIST = ["寒い", "あったまろ", "凍える", "冷たい"]

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

    if "food_ng" in detected_tags or any(word.lower() in text.lower() for word in NG_WORDS):
        logging.debug(f"🍽️ NGワード/食事検出: {text[:40]}")
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

    # 単語入力対応
    if len(text.strip()) <= 4:
        suffixes = [
            "って癒されるよね〜",
            "ってもふもふしてて好き〜",
            "ってふわふわで落ち着く〜",
            "って見てるだけで幸せ〜",
        ]
        text = f"{text.strip()}{random.choice(suffixes)}"

    examples = [
        ("寒い〜", "もふもふであったまろ〜♡"),
        ("毛布", "毛布にくるまってぬくぬくだね〜🐰"),
        ("猫", "猫って癒しのかたまりだよね〜🐾"),
        ("ぬいぐるみ", "ぎゅってしたくなるね〜💕"),
        ("雲", "もくもくしてて可愛いよね〜☁️"),
    ]
    prompt = (
        "ふわふわでやさしい返事を考えてね。\n"
        "※『もふもふであったまろ〜♡』や『癒されるよね〜』は毎回入れなくていいよ。\n"
        + "\n".join([f"{q} → {a}" for q, a in examples])
        + f"\n{text.strip()} →"
    )
    logging.debug(f"🧪 プロンプト確認: {prompt}")

    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=150).to(model.device)
    try:
        outputs = model.generate(
            **inputs,
            max_new_tokens=25,  # トークン制限を減らす
            pad_token_id=tokenizer.pad_token_id,
            do_sample=True,
            temperature=0.6,
            top_k=30,
            top_p=0.9,
            no_repeat_ngram_size=3
        )
        raw_reply = tokenizer.decode(outputs[0], skip_special_tokens=True).strip()
        logging.debug(f"🧸 Raw AI出力（生データ）: {raw_reply}")
        logging.debug(f"🧸 AI出力（クリーン後）: {clean_output(raw_reply)}")

        reply = clean_output(raw_reply)
        reply = apply_fuwamoko_tone(reply)

        if not reply or len(reply) < 5:
            logging.warning(f"⏭️ SKIP: 空または短すぎ: len={len(reply)}, テキスト: {reply[:60]}, 理由: 生成失敗")
            return random.choice(NORMAL_TEMPLATES_JP) if lang == "ja" else random.choice(NORMAL_TEMPLATES_EN)

        if not re.search(r'(です|ます|ね|よ|だ|る|た|に|を|が|は)', reply) or re.fullmatch(r'[ぁ-んー゛゜。、\s「」！？]+', reply):
            logging.warning(f"⏭️ SKIP: 文章不成立: テキスト: {reply[:60]}, 理由: 文法不十分または擬音語のみ")
            return random.choice(NORMAL_TEMPLATES_JP) if lang == "ja" else random.choice(NORMAL_TEMPLATES_EN)

        if len(reply) < 10 or len(reply) > 70:
            logging.warning(f"⏭️ SKIP: 長さ不適切: len={len(reply)}, テキスト: {reply[:60]}, 理由: 長さ超過/不足")
            return random.choice(NORMAL_TEMPLATES_JP) if lang == "ja" else random.choice(NORMAL_TEMPLATES_EN)

        for bad in NG_PHRASES:
            if re.search(bad, reply):
                logging.warning(f"⏭️ SKIP: NGフレーズ検出: {bad}, テキスト: {reply[:60]}, 理由: NGフレーズ")
                return random.choice(NORMAL_TEMPLATES_JP) if lang == "ja" else random.choice(NORMAL_TEMPLATES_EN)

        if any(word in reply for word in SEASONAL_WORDS_BLACKLIST):
            logging.warning("⏭️ SKIP: 季節不一致: 寒さ表現あり")
            return random.choice(NORMAL_TEMPLATES_JP)

        if reply.count("もふもふ") > 1:
            reply = reply.replace("もふもふ", "ふわふわ", 1)

        if not re.search(r"[🌸💕🐾☁️🐰✨♡]", reply):
            reply += " " + random.choice(["🐰", "🌸", "💕"])

        logging.info(f"🦊 AI生成成功: {reply}, 長さ: {len(reply)}")
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
        lower = np.array([5, 50, 70], dtype=np.uint8)
        upper = np.array([20, 150, 240], dtype=np.uint8)
        mask = cv2.inRange(hsv_img, lower, upper)
        skin_colors = img_np[mask > 0]

        if skin_colors.size > 0:
            avg_color = np.mean(skin_colors, axis=0)
            logging.debug(f"平均肌色: BGR={avg_color}")
            if np.mean(avg_color) > 220:
                logging.debug("→ 明るすぎるので肌色ではなく白とみなす")
                return 0.0

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
        their_followers = {f.handle for f in client.get_followers(actor=handle, limit=100).followers}
        my_followers = {f.handle for f in client.get_followers(actor=HANDLE, limit=100).followers}
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
            blob = client.get_blob(cid=cid, did=did)
            img_data = BytesIO(blob.data)
            img = Image.open(img_data)
            img.load()
            logging.info(f"🟢 Blob画像形式={img.format}, サイズ={img.size}")
            return img
        except Exception as e:
            logging.error(f"❌ Blob APIエラー: {type(e).__name__}: {e}")

    did_safe = unquote(did) if did else None
    cdn_urls = [
        f"https://cdn.bsky.app/img/feed_thumbnail/plain/{quote(did_safe)}/{quote(cid)}@jpeg" if did_safe else None,
        f"https://cdn.bsky.app/img/feed_fullsize/plain/{quote(did_safe)}/{quote(cid)}@jpeg" if did_safe else None
    ]
    headers = {"User-Agent": "Mozilla/5.0"}

    for url in [u for u in cdn_urls if u]:
        try:
            response = requests.get(url, headers=headers, timeout=10, stream=True)
            response.raise_for_status()
            img_data = BytesIO(response.content)
            img = Image.open(img_data)
            img.load()
            logging.info(f"🟢 画像形式={img.format}, サイズ={img.size}")
            return img
        except Exception as e:
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

# モデルロード（グローバルスコープに追加）
fuwamoko_model = torch.jit.load("fuwamoko_model.pt").to("cuda")  # GitHub Actions用にCPUで

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

        # PyTorch用にリサイズと前処理
        transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])
        img_tensor = transform(img).unsqueeze(0).to("cuda")

        # 推論
        with torch.no_grad():
            output = fuwamoko_model(img_tensor)
            _, predicted = torch.max(output, 1)
            category = ["other", "food", "fuwamoko"][predicted.item()]
            logging.debug(f"🧪 PyTorch推論結果: {category}")

        # 色検知も併用（バックアップ）
        resized_img = img.resize((64, 64))
        hsv_img = cv2.cvtColor(np.array(resized_img), cv2.COLOR_RGB2HSV)
        bright_colors = [(r, g, b) for (r, g, b), (_, s, v) in zip(resized_img.getdata(), hsv_img.reshape(-1, 3)) if v > 130]
        color_counts = Counter(bright_colors)
        top_colors = color_counts.most_common(5)
        logging.debug(f"トップ5カラー（明度フィルター後）: {[(c[0], c[1]) for c in top_colors]}")

        fluffy_count = 0
        bright_color_count = 0
        food_color_count = 0
        for color, _ in top_colors:
            r, g, b = color
            if is_fluffy_color(r, g, b, bright_colors):
                fluffy_count += 1
            if r > 180 and g > 180 and b > 180:
                bright_color_count += 1
            if ((150 <= r <= 200 and 150 <= g <= 200 and 150 <= b <= 200) or  # ハム/卵
                (220 <= r <= 250 and 220 <= g <= 250 and 210 <= b <= 230) or  # おにぎり
                (230 <= r <= 255 and 200 <= g <= 230 and 130 <= b <= 160) or  # 豆腐
                (r == 255 and g == 255 and b == 255)):                       # 純白
                food_color_count += 1
        logging.debug(f"ふわもこ色カウント: {fluffy_count}, 明るい色数: {bright_color_count}, 食品色数: {food_color_count}")

        skin_ratio = check_skin_ratio(img)
        food_ratio = food_color_count / 5 if top_colors else 0.0
        logging.debug(f"肌色比率: {skin_ratio:.2%}, 食品色比率: {food_ratio:.2%}, ふわもこカラー数: {fluffy_count}")

        # 最終判定
        if category == "fuwamoko" or (fluffy_count >= 2 and food_ratio <= 0.2 and skin_ratio < 0.5):
            logging.info("🟢 ふわもこ色検出またはPyTorch判定成功")
            return True
        elif category == "food" or food_ratio > 0.2:
            logging.warning(f"⏭️ スキップ: 食品色比率 {food_ratio:.2%} > 20% または PyTorch判定")
            return False
        else:
            logging.warning("⏭️ スキップ: 色条件不足またはPyTorch判定")
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
            if any(word in check_text for word in globals()["EMOTION_TAGS"]["nsfw_ng"]):
                logging.warning("⏭️ スキップ: NSFW関連検出")
                return False
        except KeyError as e:
            logging.error(f"❌ グローバル辞書エラー: {type(e).__name__}: {e}")
            return False

    except Exception as e:
        logging.error(f"❌ 画像処理エラー: {type(e).__name__}: {e} (cid={cid}, uri={getattr(post, 'uri', 'unknown')})")
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
            fuwamoko_uris[normalized_uri] = indexed_at
            logging.info(f"🟢 履歴保存: {normalized_uri}")
            with open(FUWAMOKO_FILE, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                last_line = lines[-1].strip() if lines else ""
                if last_line.startswith(normalized_uri):
                    logging.debug(f"🦊 履歴ファイル確認: 最後の行={last_line}")
                else:
                    logging.error(f"❌ 履歴保存失敗: 最後の行={last_line}")
            load_fuwamoko_uris()
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
        
def classify_text_emotion(text):
    text = text.lower()
    # NG系最優先
    for tag in ["nsfw_ng", "food_ng"]:
        for word in globals()["EMOTION_TAGS"].get(tag, []):
            if word in text:
                logging.debug(f"⚠️ '{word}' 検出 → NGタグ: {tag}")
                return tag
    # 中間ケース（髪やオーラ）
    if any(word in text for word in ["髪の毛", "オーラ", "トーク", "補正"]):
        logging.debug("△ 中間ケース検出: 髪/オーラ/トーク関連")
        return "neutral_ambiguous"  # 中間判定
    # 通常タグ
    for tag, words in globals()["EMOTION_TAGS"].items():
        if tag.endswith("_ng") or tag == "neutral_ambiguous":
            continue
        for word in words:
            if word in text:
                logging.debug(f"✅ '{word}' 検出 → タグ: {tag}")
                return tag
    return "neutral"
    
def is_suspicious_context(text, bio=""):
    suspicious_keywords = [
        "#グラビアアイドル", "#メンズエステ", "#名古屋メンエス", "#風俗", "#ご予約", "#DMで",
        "マシュマロ", "性感", "体", "谷間", "胸元", "ランジェリー", "リピ様", "リンク"
    ]
    text = text.lower()
    bio = bio.lower()
    return any(kw in text or kw in bio for kw in suspicious_keywords)

def process_post(post_data, client, fuwamoko_uris, reposted_uris):
    try:
        actual_post = post_data.post if hasattr(post_data, 'post') else post_data
        uri = str(actual_post.uri)
        post_id = uri.split('/')[-1]
        text = getattr(actual_post.record, 'text', '') if hasattr(actual_post.record, 'text') else ''
        bio = getattr(client.get_profile(actor=actual_post.author.handle), 'description', '')

        # 文脈チェック
        if is_suspicious_context(text, bio):
            logging.info(f"⏭️ スキップ: 疑わしい文脈検出: {text[:40]} ({post_id})")
            save_fuwamoko_uri(uri, actual_post.indexed_at)
            return False

        emotion = classify_text_emotion(text)
        if emotion.endswith("_ng") or emotion == "neutral_ambiguous":
            logging.info(f"⏭️ スキップ: NGまたは中間判定（{emotion}）: {text[:40]} ({post_id})")
            save_fuwamoko_uri(uri, actual_post.indexed_at)
            return False

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
                        save_fuwamoko_uri(uri, indexed_at)
                        return False
                    lang = detect_language(client, author)
                    reply_text = open_calm_reply("", text, lang=lang)
                    if not reply_text:
                        print(f"⏭️ スキップ: 返信生成失敗: {post_id}")
                        logging.debug(f"スキップ: 返信生成失敗: {post_id}")
                        save_fuwamoko_uri(uri, indexed_at)
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
                    save_fuwamoko_uri(uri, indexed_at)
                    print(f"✅ SUCCESS: 返信成功: @{author} ({post_id})")
                    logging.info(f"🟢 返信成功: @{author} ({post_id})")
                    return True
                else:
                    print(f"⏭️ スキップ: ふわもこ画像でない: {post_id} (画像 {i+1})")
                    logging.warning(f"⏭️ スキップ: ふわもこ画像でない: {post_id} (画像 {i+1})")
                    save_fuwamoko_uri(uri, indexed_at)
                    return False
            except Exception as e:
                print(f"❌ 画像処理エラー: {type(e).__name__}: {e} ({post_id}, uri={uri}, cid={actual_post.cid})")
                logging.error(f"❌ 画像処理エラー: {type(e).__name__}: {e} ({post_id}, uri={uri}, cid={actual_post.cid})")
                save_fuwamoko_uri(uri, indexed_at)
                return False
    except Exception as e:
        print(f"❌ 投稿処理エラー: {type(e).__name__}: {e} ({post_id}, uri={uri})")
        logging.error(f"❌ 投稿処理エラー: {type(e).__name__}: {e} ({post_id}, uri={uri})")
        save_fuwamoko_uri(uri, indexed_at)
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