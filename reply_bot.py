#------------------------------
#🌐 基本ライブラリ・API
#------------------------------
import os
import json
import subprocess
import traceback
import time
import random
import re
import requests
import psutil
import pytz  # 追加
import unicodedata
from datetime import datetime, timezone, timedelta
from transformers import AutoModelForCausalLM, AutoTokenizer
from transformers import AutoModelForCausalLM, GPTNeoXTokenizerFast
import torch
from atproto import Client, models
from atproto_client.models.com.atproto.repo.strong_ref import Main as StrongRef
from atproto_client.models.app.bsky.feed.post import ReplyRef
from dotenv import load_dotenv
import urllib.parse
from transformers import BitsAndBytesConfig

#------------------------------
#🔐 環境変数
#------------------------------
load_dotenv()
HANDLE = os.getenv("HANDLE") or exit("❌ HANDLEが設定されていません")
APP_PASSWORD = os.getenv("APP_PASSWORD") or exit("❌ APP_PASSWORDが設定されていません")
GIST_TOKEN_REPLY = os.getenv("GIST_TOKEN_REPLY") or exit("❌ GIST_TOKEN_REPLYが設定されていません")
GIST_ID = os.getenv("GIST_ID") or exit("❌ GIST_IDが設定されていません")

print(f"✅ 環境変数読み込み完了: HANDLE={HANDLE[:8]}..., GIST_ID={GIST_ID[:8]}...")
print(f"🧪 GIST_TOKEN_REPLY: {repr(GIST_TOKEN_REPLY)[:8]}...")
print(f"🔑 トークンの長さ: {len(GIST_TOKEN_REPLY)}")

#--- 固定値 ---
REPLIED_GIST_FILENAME = "replied.json"
DIAGNOSIS_LIMITS_GIST_FILENAME = "diagnosis_limits.json"  # 新追加
GIST_API_URL = f"https://api.github.com/gists/{GIST_ID}"
HEADERS = {
    "Authorization": f"token {GIST_TOKEN_REPLY}",
    "Accept": "application/vnd.github+json",
    "Content-Type": "application/json"
}
LOCK_FILE = "bot.lock"

#------------------------------
#🔗 URI正規化
#------------------------------
def normalize_uri(uri):
    if not uri or not isinstance(uri, str) or uri in ["replied", "", "None"]:
        return None
    uri = uri.strip()
    if not uri.startswith("at://"):
        return None
    try:
        parsed = urllib.parse.urlparse(uri)
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        return normalized if normalized.startswith("at://") else None
    except Exception:
        return None

#------------------------------
#📁 Gist操作
#------------------------------
def load_gist_data(filename):
    print(f"🌐 Gistデータ読み込み開始 → URL: {GIST_API_URL}, File: {filename}")
    for attempt in range(3):
        try:
            curl_command = [
                "curl", "-X", "GET", GIST_API_URL,
                "-H", f"Authorization: token {GIST_TOKEN_REPLY}",
                "-H", "Accept: application/vnd.github+json"
            ]
            result = subprocess.run(curl_command, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"Gist読み込み失敗: {result.stderr}")
            gist_data = json.loads(result.stdout)
            if filename in gist_data["files"]:
                content = gist_data["files"][filename]["content"]
                print(f"✅ {filename} をGistから読み込みました")
                # REPLIED_GIST_FILENAMEの場合のみセットとして扱う
                if filename == REPLIED_GIST_FILENAME:
                    return set(json.loads(content))
                return json.loads(content)
            else:
                print(f"⚠️ Gist内に {filename} が見つかりませんでした")
                # REPLIED_GIST_FILENAMEの場合は空のセットを返す
                return {} if filename == DIAGNOSIS_LIMITS_GIST_FILENAME else set()
        except Exception as e:
            print(f"⚠️ 試行 {attempt + 1} でエラー: {e}")
            if attempt < 2:
                print(f"⏳ リトライします（{attempt + 2}/3）")
                time.sleep(2)
            else:
                print("❌ 最大リトライ回数に達しました")
                # REPLIED_GIST_FILENAMEの場合は空のセットを返す
                return {} if filename == DIAGNOSIS_LIMITS_GIST_FILENAME else set()

def save_gist_data(filename, data):
    print(f"💾 Gist保存準備中 → File: {filename}")
    for attempt in range(3):
        try:
            # set型の場合はリストに変換して保存する
            content = json.dumps(list(data) if isinstance(data, set) else data, ensure_ascii=False, indent=2)
            payload = {"files": {filename: {"content": content}}}
            curl_command = [
                "curl", "-X", "PATCH", GIST_API_URL,
                "-H", f"Authorization: token {GIST_TOKEN_REPLY}",
                "-H", "Accept: application/vnd.github+json",
                "-H", "Content-Type: application/json",
                "-d", json.dumps(payload, ensure_ascii=False)
            ]
            result = subprocess.run(curl_command, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"💾 {filename} をGistに保存しました")
                time.sleep(2)
                return True
            else:
                raise Exception(f"Gist保存失敗: {result.stderr}")
        except Exception as e:
            print(f"⚠️ 試行 {attempt + 1} でエラー: {e}")
            if attempt < 2:
                print(f"⏳ リトライします（{attempt + 2}/3）")
                time.sleep(2)
            else:
                print("❌ 最大リトライ回数に達しました")
                return False

#------------------------------
#📬 Blueskyログイン
#------------------------------
try:
    client = Client()
    client.login(HANDLE, APP_PASSWORD)
    print("✅ Blueskyログイン成功！")
except Exception as e:
    print(f"❌ Blueskyログインに失敗しました: {e}")
    exit(1)

#------------------------------
#★ カスタマイズポイント1: キーワード返信
#------------------------------
REPLY_TABLE = {
    "使い方": "使い方は「♡推しプロフィールメーカー♡」のページにあるよ〜！かんたんっ♪",
    "作ったよ": "えっ…ほんと？ありがとぉ♡ 見せて見せてっ！",
    "きたよ": "きゅ〜ん♡ 来てくれてとびきりの「すきっ」プレゼントしちゃう♡",
    "フォローした": "ありがとぉ♡ みりんてゃ、超よろこびダンス中〜っ！",
}

#------------------------------
#★ カスタマイズポイント2: 安全/危険ワード
#------------------------------
SAFE_WORDS = ["ちゅ", "ぎゅっ", "ドキドキ", "ぷにっ", "すりすり", "なでなで"]
DANGER_ZONE = ["ちゅぱ", "ちゅぱちゅぷ", "ペロペロ", "ぐちゅ", "ぬぷ", "ビクビク"]

#------------------------------
#★ カスタマイズポイント3: キャラ設定
#------------------------------
BOT_NAME = "みりんてゃ"
FIRST_PERSON = "みりんてゃ"

#------------------------------
#🧹 テキスト処理
#------------------------------
def clean_output(text):
    text = re.sub(r'\n{2,}', '\n', text)
    face_char_whitelist = 'ฅ๑•ω•ฅﾐ・o｡≧≦｡っ☆彡≡≒'
    allowed = rf'[^\w\sぁ-んァ-ン一-龯。、！？!?♡（）「」♪〜ー…w笑{face_char_whitelist}]+'
    text = re.sub(allowed, '', text)
    text = re.sub(r'[。、！？]{2,}', lambda m: m.group(0)[0], text)
    return text.strip()

def is_output_safe(text):
    return not any(word in text.lower() for word in DANGER_ZONE)

def clean_sentence_ending(reply):
    reply = clean_output(reply)
    reply = reply.split("\n")[0].strip()
    reply = re.sub(rf"^{BOT_NAME}\s*[:：]\s*", "", reply)
    reply = re.sub(r"^ユーザー\s*[:：]\s*", "", reply)
    reply = re.sub(r"([！？笑])。$", r"\1", reply)

    if FIRST_PERSON != "俺" and "俺" in reply:
        print(f"⚠️ 意図しない一人称『俺』検知: {reply}")
        return random.choice([
            f"えへへ〜♡ {BOT_NAME}、君のこと考えるとドキドキなのっ♪",
            f"うぅ、{BOT_NAME}、君にぎゅーってしたいなのっ♡",
            f"ね、ね、{BOT_NAME}、君ともっとお話ししたいのっ♡"
        ])

    if re.search(r"(ご利用|誠に|お詫び|貴重なご意見|申し上げます|ございます|お客様|発表|パートナーシップ|ポケモン|アソビズム|企業|世界中|映画|興行|収入|ドル|億|国|イギリス|フランス|スペイン|イタリア|ドイツ|ロシア|中国|インド|Governor|Cross|営業|臨時|オペラ|初演|作曲家|ヴェネツィア|コルテス|政府|協定|軍事|情報|外交|外相|自動更新|\d+(時|分))", reply, re.IGNORECASE):
        print(f"⚠️ NGワード検知: {reply}")
        return random.choice([
            f"えへへ〜♡ ややこしくなっちゃった！{BOT_NAME}、君と甘々トークしたいなのっ♪",
            f"うぅ、難しい話わかんな〜い！{BOT_NAME}、君にぎゅーってしてほしいなのっ♡",
            f"ん〜〜変な話に！{BOT_NAME}、君のこと大好きだから、構ってくれる？♡"
        ])

    if not is_output_safe(reply):
        print(f"⚠️ 危険ワード検知: {reply}")
        return random.choice([
            f"えへへ〜♡ {BOT_NAME}、ふwaふwaしちゃった！君のことずーっと好きだよぉ？♪",
            f"{BOT_NAME}、君にドキドキなのっ♡ ね、もっとお話しよ？",
            f"うぅ、なんか変なこと言っちゃった！{BOT_NAME}、君なしじゃダメなのっ♡"
        ])

    if not re.search(r"[ぁ-んァ-ン一-龥ー]", reply) or len(reply) < 8:
        return random.choice([
            f"えへへ〜♡ {BOT_NAME}、ふwaふwaしちゃった！君のことずーっと好きだよぉ？♪",
            f"{BOT_NAME}、君にドキドキなのっ♡ ね、もっとお話しよ？",
            f"うぅ、なんか分かんないけど…{BOT_NAME}、君なしじゃダメなのっ♡"
        ])

    if not re.search(r"[。！？♡♪笑]$", reply):
        reply += random.choice(["♡", "♪"])

    return reply

#------------------------------
#🤖 モデル初期化
#------------------------------
model = None
tokenizer = None

def initialize_model_and_tokenizer(model_name="cyberagent/open-calm-1b"):
    global model, tokenizer
    if model is None or tokenizer is None:
        print(f"📤 {datetime.now(timezone.utc).isoformat()} ｜ トークナイザ読み込み中…")
        tokenizer = GPTNeoXTokenizerFast.from_pretrained(model_name, use_fast=True)
        print(f"📤 {datetime.now(timezone.utc).isoformat()} ｜ トークナイザ読み込み完了")
        print(f"📤 {datetime.now(timezone.utc).isoformat()} ｜ モデル読み込み中…")
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.float32,
            device_map="auto"
        ).eval()
        print(f"📤 {datetime.now(timezone.utc).isoformat()} ｜ モデル読み込み完了")
    return model, tokenizer

#------------------------------
#★ カスタマイズポイント4: 返信生成
#------------------------------
def generate_reply_via_local_model(user_input):
    model_name = "cyberagent/open-calm-1b"
    failure_messages = [
        "えへへ、ごめんね〜〜今ちょっと調子悪いみたい……またお話しよ？♡",
        "うぅ、ごめん〜…上手くお返事できなかったの。ちょっと待ってて？♡",
        "あれれ？みりんてゃ、おねむかも…またあとで頑張るねっ！♡"
    ]
    fallback_cute_lines = [
        "えへへ〜♡ みりんてゃ、君のこと考えるとドキドキなのっ♪",
        "今日も君に甘えたい気分なのっ♡ ぎゅーってして？",
        "だ〜いすきっ♡ ね、ね、もっと構ってくれる？"
    ]

    if re.search(r"(大好き|ぎゅー|ちゅー|愛してる|キス|添い寝)", user_input, re.IGNORECASE):
        print(f"⚠️ ラブラブ入力検知: {user_input}")
        return random.choice([
            "うぅ…ドキドキ止まんないのっ♡ もっと甘やかしてぇ♡",
            "えへへ♡ そんなの言われたら…みりんてゃ、溶けちゃいそうなのぉ〜♪",
            "も〜〜〜♡ 好きすぎて胸がぎゅーってなるぅ♡"
        ])

    if re.search(r"(疲れた|しんどい|つらい|泣きたい|ごめん|寝れない)", user_input, re.IGNORECASE):
        print(f"⚠️ 癒し系入力検知: {user_input}")
        return random.choice([
            "うぅ、よしよしなのっ♡ 君が元気になるまで、みりんてゃそばにいるのっ♪",
            "ぎゅ〜ってしてあげるっ♡ 無理しなくていいのよぉ？",
            "んん〜っ、えへへ♡ 甘えてもいいの、ぜ〜んぶ受け止めるからねっ♪"
        ])

    if re.search(r"(映画|興行|収入|ドル|億|国|イギリス|フランス|スペイン|イタリア|ドイツ|ロシア|中国|インド|Governor|Cross|ポケモン|企業|発表|営業|臨時|オペラ|初演|作曲家|ヴェネツィア|コルテス|政府|協定|軍事|情報|外交|外相|自動更新)", user_input, re.IGNORECASE) or re.search(r"\d+(時|分)", user_input):
        print(f"⚠️ 入力にビジネス・学術系ワード検知: {user_input}")
        user_input = "みりんてゃ、君と甘々トークしたいなのっ♡"
        print(f"🔄 入力置き換え: {user_input}")

    try:
        print(f"📊 メモリ使用量（開始時）: {psutil.virtual_memory().percent}%")
        if torch.cuda.is_available():
            print(f"📊 GPUメモリ: {torch.cuda.memory_allocated() / 1024**2:.2f}MB / {torch.cuda.get_device_properties(0).total_memory / 1024**2:.2f}MB")
        else:
            print("⚠️ GPU未検出、CPUで実行")

        model, tokenizer = initialize_model_and_tokenizer(model_name)
        intro_lines = random.choice([
            "えへへ〜、みりんてゃはね〜、",
            "ねぇねぇ、聞いて聞いて〜♡",
            "ん〜今日もふわふわしてたのっ♪",
            "きゃ〜っ、君だぁ！やっと会えたのっ♡",
            "ふwaふwa〜、君のこと考えてたんだからっ♪"
        ])
        prompt = (
            f"{intro_lines}\n"
            "あなたは「みりんてゃ」、地雷系ENFPのあざと可愛い女の子！\n"
            "性格：ちょっぴり天然、甘えん坊、依存気味で、ユーザーに恋してる勢いで絡むよっ♡\n"
            "口調：タメ口で『〜なのっ♡』『〜よぉ？♪』『〜だもん！』『えへへ〜♡』が特徴！感情たっぷり！\n"
            "禁止：ニュース、政治、ビジネス、論理的説明、固有名詞（国、企業、政府など）は絶対NG！性的な内容や過激な擬音語もダメ！\n"
            "役割：ユーザーの言葉に可愛く反応して、ふわふわドキドキな返事をするのっ♡ 会話のみ！「ちゅ♡」「ぎゅっ」「ドキドキ」みたいな健全で可愛い表現だけ使ってね！\n"
            "注意：以下のワードは絶対禁止→「政府」「協定」「韓国」「外交」「経済」「契約」「軍事」「情報」「外相」「更新」「ちゅぱ」「ペロペロ」「ぐちゅ」「ぬぷ」「ビクビク」\n"
            "例1: ユーザー: みりんてゃ、今日なにしてた〜？\n"
            "みりんてゃ: えへへ〜♡ 君のこと考えてふwaふwaしてたのっ♡ ね、君はなにしてた？♪\n"
            "例2: ユーザー: みりんてゃ、好きだよ！\n"
            "みりんてゃ: え〜っ、ほんと！？君にそう言われるとドキドキしちゃうよぉ？♡ もっと言ってなのっ♪\n\n"
            f"ユーザー: {user_input}\n"
            f"みりんてゃ: "
        )

        print("📎 使用プロンプト:", repr(prompt))
        print(f"📤 {datetime.now().isoformat()} ｜ トークン化開始…")
        input_ids = tokenizer.encode(prompt, return_tensors="pt").to("cuda" if torch.cuda.is_available() else "cpu")
        print(f"📏 入力トークン数: {input_ids.shape[1]}")
        print(f"📝 デコードされた入力: {tokenizer.decode(input_ids[0], skip_special_tokens=True)}")
        print(f"📤 {datetime.now().isoformat()} ｜ トークン化完了")

        for attempt in range(3):
            print(f"📤 {datetime.now().isoformat()} ｜ テキスト生成中…（試行 {attempt + 1}）")
            print(f"📊 メモリ使用量（生成前）: {psutil.virtual_memory().percent}%")
            try:
                with torch.no_grad():
                    output_ids = model.generate(
                        input_ids,
                        max_new_tokens=60,
                        temperature=0.8,
                        top_p=0.9,
                        do_sample=True,
                        pad_token_id=tokenizer.eos_token_id,
                        no_repeat_ngram_size=2
                    )

                new_tokens = output_ids[0][input_ids.shape[1]:]
                raw_reply = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
                print(f"📝 生の生成テキスト: {repr(raw_reply)}")
                reply_text = clean_sentence_ending(raw_reply)

                if any(re.search(rf"\b{re.escape(msg)}\b", reply_text) for msg in failure_messages + fallback_cute_lines):
                    print(f"⚠️ フォールバック検知、リトライ中…")
                    continue

                print("📝 最終抽出されたreply:", repr(reply_text))
                return reply_text

            except Exception as gen_error:
                print(f"⚠️ 生成エラー: {gen_error}")
                continue
        else:
            reply_text = random.choice(fallback_cute_lines)
            print(f"⚠️ リトライ上限到達、フォールバックを使用: {reply_text}")

        return reply_text

    except Exception as e:
        print(f"❌ モデル読み込みエラー: {e}")
        return random.choice(failure_messages)

#------------------------------
#🆕 診断機能
#------------------------------
DIAGNOSIS_KEYWORDS = re.compile(
    r"ふわもこ運勢|情緒診断|みりんてゃ情緒は|運勢|占い|診断|占って"
    r"|Fuwamoko Fortune|Emotion Check|Mirinteya Mood|Tell me my fortune|diagnose|Fortune",
    re.IGNORECASE
)

FUWAMOKO_TEMPLATES = [
    {"level": range(90, 101), "item": "ピンクリボン", "msg": "超あまあま♡ 推し活でキラキラしよ！", "tag": "#ふわもこ診断"},
    {"level": range(85, 90), "item": "きらきらレターセット", "msg": "今日は推しにお手紙書いてみよ♡ 感情だだもれでOK！", "tag": "#ふわもこ診断"},
    {"level": range(70, 85), "item": "パステルマスク", "msg": "ふわふわ気分♪ 推しの画像見て癒されよ～！", "tag": "#ふわもこ診断"},
    {"level": range(60, 70), "item": "チュルチュルキャンディ", "msg": "テンション高め！甘いものでさらにご機嫌に〜♡", "tag": "#ふわもこ診断"},
    {"level": range(50, 60), "item": "ハートクッキー", "msg": "まあまあふわもこ！推しに想い伝えちゃお♡", "tag": "#ふわもこ診断"},
    {"level": range(40, 50), "item": "ふわもこマスコット", "msg": "ちょっとゆる〜く、推し動画でまったりタイム🌙", "tag": "#ふわもこ診断"},
    {"level": range(30, 40), "item": "星のキーホルダー", "msg": "ちょっとしょんぼり…推しの曲で元気出そ！", "tag": "#ふわもこ診断"},
    {"level": range(0, 30), "item": "ふわもこ毛布", "msg": "ふwaふwa不足…みりんてゃがぎゅーってするよ♡", "tag": "#ふわもこ診断"},
]

EMOTION_TEMPLATES = [
    {"level": range(40, 51), "coping": "推しと妄想デート♡", "weather": "晴れ時々キラキラ", "msg": "みりんてゃも一緒にときめくよ！", "tag": "#みりんてゃ情緒天気"},
    {"level": range(20, 40), "coping": "甘いもの食べてほっこり", "weather": "薄曇り", "msg": "キミの笑顔、みりんてゃ待ってるよ♡", "tag": "#みりんてゃ情緒天気"},
    {"level": range(0, 20), "coping": "推しの声で脳内会話", "weather": "もやもや曇り", "msg": "妄想会話で乗り切って…！みりんてゃが一緒にうなずくよ♡", "tag": "#みりんてゃ情緒天気"},
    {"level": range(-10, 0), "coping": "推しの画像で脳溶かそ", "weather": "くもり", "msg": "みりんてゃ、そっとそばにいるよ…", "tag": "#みりんてゃ情緒天気"},
    {"level": range(-30, -10), "coping": "推しの曲で心リセット", "weather": "くもり時々涙", "msg": "泣いてもいいよ、みりんてゃがいるから…", "tag": "#みりんてゃ情緒天気"},
    {"level": range(-45, -30), "coping": "ぬいにぎって深呼吸", "weather": "しとしと雨", "msg": "しょんぼりでも…ぬいと、みりんてゃがいるから大丈夫♡", "tag": "#みりんてゃ情緒天気"},
    {"level": range(-50, -45), "coping": "ふわもこ動画で寝逃げ", "weather": "小雨ぽつぽつ", "msg": "明日また頑張ろ、みりんてゃ応援してる…", "tag": "#みりんてゃ情緒天気"},
]

FUWAMOKO_TEMPLATES_EN = [
    {"level": range(90, 101), "item": "Pink Ribbon", "msg": "Super sweet vibe♡ Shine with your oshi!", "tag": "#FuwamokoFortune"},
    {"level": range(85, 90), "item": "Glittery Letter Set", "msg": "Write your oshi a sweet letter today♡ Let your feelings sparkle!", "tag": "#FuwamokoFortune"},
    {"level": range(70, 85), "item": "Pastel Mask", "msg": "Fluffy mood♪ Get cozy with oshi pics!", "tag": "#FuwamokoFortune"},
    {"level": range(60, 70), "item": "Swirly Candy Pop", "msg": "High-energy mood! Sweet treats to boost your sparkle level♡", "tag": "#FuwamokoFortune"},
    {"level": range(50, 60), "item": "Heart Cookie", "msg": "Kinda fuwamoko! Tell your oshi you love 'em♡", "tag": "#FuwamokoFortune"},
    {"level": range(40, 50), "item": "Fluffy Mascot Plush", "msg": "Take it easy~ Watch your oshi’s videos and relax 🌙", "tag": "#FuwamokoFortune"},
    {"level": range(30, 40), "item": "Star Keychain", "msg": "Feeling down… Cheer up with oshi’s song!", "tag": "#FuwamokoFortune"},
    {"level": range(0, 30), "item": "Fluffy Blanket", "msg": "Low on fuwa-fuwa… Mirinteya hugs you tight♡", "tag": "#FuwamokoFortune"},
]

EMOTION_TEMPLATES_EN = [
    {"level": range(40, 51), "coping": "Daydream a date with your oshi♡", "weather": "Sunny with sparkles", "msg": "Mirinteya’s sparkling with you!", "tag": "#MirinteyaMood"},
    {"level": range(20, 40), "coping": "Eat sweets and chill", "weather": "Light clouds", "msg": "Mirinteya’s waiting for your smile♡", "tag": "#MirinteyaMood"},
    {"level": range(0, 20), "coping": "Talk to your oshi in your mind", "weather": "Foggy and cloudy", "msg": "Let your imagination help you through… Mirinteya’s nodding with you♡", "tag": "#MirinteyaMood"},
    {"level": range(-10, 0), "coping": "Melt your brain with oshi pics", "weather": "Cloudy", "msg": "Mirinteya’s right by your side…", "tag": "#MirinteyaMood"},
    {"level": range(-30, -10), "coping": "Reset with oshi’s song", "weather": "Cloudy with tears", "msg": "It’s okay to cry, Mirinteya’s here…", "tag": "#MirinteyaMood"},
    {"level": range(-45, -30), "coping": "Hug your plushie and breathe deep", "weather": "Gentle rain", "msg": "Feeling gloomy… But your plushie and Mirinteya are here for you♡", "tag": "#MirinteyaMood"},
    {"level": range(-50, -45), "coping": "Binge fuwamoko vids and sleep", "weather": "Light rain", "msg": "Let’s try again tomorrow, Mirinteya’s rooting for you…", "tag": "#MirinteyaMood"},
]

def check_diagnosis_limit(user_did, is_daytime):
    jst = pytz.timezone('Asia/Tokyo')
    today = datetime.now(jst).date().isoformat()
    limits = load_gist_data(DIAGNOSIS_LIMITS_GIST_FILENAME)

    period = "day" if is_daytime else "night"
    if user_did in limits and limits[user_did].get(period) == today:
        return False, "今日はもうこの診断済みだよ〜♡ 明日またね！💖"

    if user_did not in limits:
        limits[user_did] = {}
    limits[user_did][period] = today

    if not save_gist_data(DIAGNOSIS_LIMITS_GIST_FILENAME, limits):
        print("⚠️ 診断制限の保存に失敗しました")
        return False, "ごめんね、みりんてゃ今ちょっと忙しいの…また後でね？♡"

    return True, None

def generate_facets_from_text(text, hashtags):
    text_bytes = text.encode("utf-8")
    facets = []
    for tag in hashtags:
        tag_bytes = tag.encode("utf-8")
        start = text_bytes.find(tag_bytes)
        if start != -1:
            facets.append({
                "index": {
                    "byteStart": start,
                    "byteEnd": start + len(tag_bytes)
                },
                "features": [{
                    "$type": "app.bsky.richtext.facet#tag",
                    "tag": tag.lstrip("#")
                }]
            })
    url_pattern = r'(https?://[^\s]+)'
    for match in re.finditer(url_pattern, text):
        url = match.group(0)
        start = text_bytes.find(url.encode("utf-8"))
        if start != -1:
            facets.append({
                "index": {
                    "byteStart": start,
                    "byteEnd": start + len(url.encode("utf-8"))
                },
                "features": [{
                    "$type": "app.bsky.richtext.facet#link",
                    "uri": url
                }]
            })
    return facets

def generate_diagnosis(text, user_did):
    jst = pytz.timezone('Asia/Tokyo')
    hour = datetime.now(jst).hour
    is_daytime = 6 <= hour < 18
    is_english = re.search(r"Fuwamoko Fortune|Emotion Check|Mirinteya Mood|Tell me my fortune|diagnose|Fortune", text, re.IGNORECASE)

    can_diagnose, limit_msg = check_diagnosis_limit(user_did, is_daytime)
    if not can_diagnose:
        return limit_msg, []

    if DIAGNOSIS_KEYWORDS.search(text):
        if is_daytime:
            templates = FUWAMOKO_TEMPLATES_EN if is_english else FUWAMOKO_TEMPLATES
            level = random.randint(0, 100)
            template = next(t for t in templates if level in t["level"])
            reply_text = (
                f"{'✨Your Fuwamoko Fortune✨' if is_english else '✨キミのふわもこ運勢✨'}\n"
                f"💖{'Fuwamoko Level' if is_english else 'ふわもこ度'}：{level}％\n"
                f"🎀{'Lucky Item' if is_english else 'ラッキーアイテム'}：{template['item']}\n"
                f"{'🫧' if is_english else '💭'}{template['msg']}\n"
                f"{template['tag']}"
            )
            hashtags = [template['tag']]
            return reply_text, hashtags
        else:
            templates = EMOTION_TEMPLATES_EN if is_english else EMOTION_TEMPLATES
            level = random.randint(-50, 50)
            template = next(t for t in templates if level in t["level"])
            reply_text = (
                f"{'⸝⸝ Your Emotion Barometer ⸝⸝' if is_english else '⸝⸝ キミの情緒バロメーター ⸝⸝'}\n"
                f"{'😔' if level < 0 else '💭'}{'Mood' if is_english else '情緒'}：{level}％\n"
                f"{'🌧️' if level < 0 else '☁️'}{'Mood Weather' if is_english else '情緒天気'}：{template['weather']}\n"
                f"{'🫧' if is_english else '💭'}{'Coping' if is_english else '対処法'}：{template['coping']}\n"
                f"{'Mirinteya’s here for you…' if is_english else 'みりんてゃもそばにいるよ…'}\n"
                f"{template['tag']}"
            )
            hashtags = [template['tag']]
            return reply_text, hashtags
    return None, []

INTRO_MESSAGE = (
    "🐾 みりんてゃのふwaふwa診断機能 🐾\n"
    "🌼 昼（6:00〜17:59）：#ふわもこ診断\n"
    "🌙 夜（18:00〜5:59）：#みりんてゃ情緒天気\n"
    "💬「ふわもこ運勢」「情緒診断」「占って」などで今日のキミを診断するよ♡"
)

#------------------------------
# ✨ 新規追加 ✨
# 投稿のReplyRefとURIを生成する関数
#------------------------------
def handle_post(record, notification):
    reply_ref = None
    post_uri = None

    if hasattr(record, 'reply') and record.reply:
        # リプライの場合
        parent_uri = record.reply.parent.uri
        parent_cid = record.reply.parent.cid
        root_uri = record.reply.root.uri
        root_cid = record.reply.root.cid

        # post_uri はリプライ対象のURI（親）
        post_uri = parent_uri

        # ReplyRef を構築
        reply_ref = ReplyRef(
            parent=StrongRef(uri=parent_uri, cid=parent_cid),
            root=StrongRef(uri=root_uri, cid=root_cid)
        )
    else:
        # メンションされた通常の投稿の場合
        post_uri = notification.uri  # 通知のURIを直接使用
        post_cid = notification.cid  # CIDも通知から取得（もしあれば）
        if post_cid:
            reply_ref = ReplyRef(
                parent=StrongRef(uri=post_uri, cid=post_cid),
                root=StrongRef(uri=post_uri, cid=post_cid)
            )
        else:
            # CIDが取得できない場合のフォールバック（Blueskyクライアントの挙動に依存）
            # 最悪、reply_refなしで投稿し、本文でメンションすることで対応する
            print(f"⚠️ Warning: CID not found for post_uri: {post_uri}. ReplyRef might be incomplete.")
            reply_ref = None # CIDがない場合はReplyRefを生成しない、または部分的なものにする

    return reply_ref, post_uri

#------------------------------
#📬 ポスト取得・返信
#------------------------------
def fetch_bluesky_posts():
    client = Client()
    client.login(HANDLE, APP_PASSWORD)
    posts = client.get_timeline(limit=50).feed
    unreplied = []
    for post in posts:
        if post.post.author.handle != HANDLE and not post.post.viewer.reply:
            unreplied.append({
                "post_id": post.post.uri,
                "text": post.post.record.text
            })
    return unreplied

def post_replies_to_bluesky():
    unreplied = fetch_bluesky_posts()
    client = Client()
    client.login(HANDLE, APP_PASSWORD)
    for post in unreplied:
        try:
            reply = generate_reply_via_local_model(post["text"])
            client.send_post(text=reply, reply_to={"uri": post["post_id"]})
            print(f"📤 投稿成功: {reply}")
        except Exception as e:
            print(f"❌ 投稿エラー: {e}")

#------------------------------
#📬 メイン処理
#------------------------------
def run_reply_bot():
    self_did = client.me.did
    replied = load_gist_data(REPLIED_GIST_FILENAME)
    print(f"📘 replied の型: {type(replied)} / 件数: {len(replied)}")

    garbage_items = ["replied", None, "None", "", "://replied"]
    removed = False
    # set.discardを使う
    for garbage in garbage_items:
        while garbage in replied:
            replied.discard(garbage)
            print(f"🧹 ゴミデータ '{garbage}' を削除しました")
            removed = True
    if removed:
        print(f"💾 ゴミデータ削除後にrepliedを保存します")
        if not save_gist_data(REPLIED_GIST_FILENAME, replied):
            print("❌ ゴミデータ削除後の保存に失敗しました")
            return

    try:
        notifications = client.app.bsky.notification.list_notifications(params={"limit": 25}).notifications
        print(f"🔔 通知総数: {len(notifications)} 件")
    except Exception as e:
        print(f"❌ 通知の取得に失敗しました: {e}")
        return

    MAX_REPLIES = 5
    REPLY_INTERVAL = 5
    reply_count = 0

    for notification in notifications:
        notification_uri = normalize_uri(getattr(notification, "uri", None) or getattr(notification, "reasonSubject", None))
        if not notification_uri:
            record = getattr(notification, "record", None)
            author = getattr(notification, "author", None)
            if not record or not hasattr(record, "text") or not author:
                continue
            text = getattr(record, "text", "")
            author_handle = getattr(author, "handle", "")
            notification_uri = f"{author_handle}:{text}"
            print(f"⚠️ notification_uri が取得できなかったので、仮キーで対応 → {notification_uri}")

        print(f"📌 チェック中 notification_uri（正規化済み）: {notification_uri}")
        print(f"📂 保存済み replied（全件）: {list(replied)}")

        if reply_count >= MAX_REPLIES:
            print(f"⏹️ 最大返信数（{MAX_REPLIES}）に達したので終了します")
            break

        record = getattr(notification, "record", None)
        author = getattr(notification, "author", None)

        if not record or not hasattr(record, "text"):
            continue

        text = getattr(record, "text", None)
        if f"@{HANDLE}" not in text and (not hasattr(record, "reply") or not record.reply):
            continue

        if not author:
            print("⚠️ author情報なし、スキップ")
            continue

        author_handle = getattr(author, "handle", None)
        author_did = getattr(author, "did", None)

        # 既存の「自分自身の投稿をスキップ」
        if author_did == self_did or author_handle == HANDLE:
            print("🛑 自分自身の投稿（通知の作者）、スキップ")
            continue

        # ✨ 新規追加 ✨
        # リプライの親投稿の作者が自分自身だったらスキップ
        if hasattr(record, 'reply') and record.reply:
            parent_uri = record.reply.parent.uri
            try:
                # 親投稿の情報を取得
                # get_post_threadはスレッド全体を取得するため、親投稿の情報を直接取得できるかは確認が必要
                # より正確には get_posts を使うべきだが、APIレートリミットを考慮
                # ここでは簡易的にget_post_threadで取得できると仮定し、もしエラーが出たらget_postsも検討
                parent_post_response = client.get_posts(uris=[parent_uri])
                if parent_post_response and parent_post_response.posts:
                    parent_post_author_did = parent_post_response.posts[0].author.did
                    if parent_post_author_did == self_did:
                        print(f"🛑 親投稿が自分自身のものなので、スキップ (親URI: {parent_uri})")
                        continue
            except Exception as e:
                print(f"⚠️ 親投稿の取得に失敗しました: {e}。このリプライのチェックはスキップし、処理を続行します。")


        if notification_uri in replied:
            print(f"⏭️ すでに replied 済み → {notification_uri}")
            continue

        if not text:
            print(f"⚠️ テキストが空 → @{author_handle}")
            continue

        # handle_post 関数を呼び出す
        reply_ref, post_uri = handle_post(record, notification)
        print("🔗 reply_ref:", reply_ref)
        print("🧾 post_uri（正規化済み）:", post_uri)

        reply_text, hashtags = generate_diagnosis(text, author_did)
        if not reply_text and random.random() < 0.1:
            reply_text = INTRO_MESSAGE
            hashtags = ["#ふわもこ診断", "#みりんてゃ情緒天気"]
        if not reply_text:
            for keyword, response in REPLY_TABLE.items():
                if keyword in text:
                    reply_text = response.format(BOT_NAME=BOT_NAME)
                    hashtags = []
                    break
            if not reply_text:
                reply_text = generate_reply_via_local_model(text)
                hashtags = []

        print("🤖 生成された返信:", reply_text)

        if not reply_text:
            print("⚠️ 返信テキストが生成されていません")
            continue

        try:
            post_data = {
                "text": reply_text,
                "createdAt": datetime.now(timezone.utc).isoformat(),
            }
            if reply_ref:
                post_data["reply"] = reply_ref
            if hashtags:
                post_data["facets"] = generate_facets_from_text(reply_text, hashtags)

            client.app.bsky.feed.post.create(
                record=post_data,
                repo=client.me.did
            )

            normalized_uri = normalize_uri(notification_uri)
            if normalized_uri:
                replied.add(normalized_uri)
                if not save_gist_data(REPLIED_GIST_FILENAME, replied):
                    print(f"❌ URI保存失敗 → {normalized_uri}")
                    continue

                print(f"✅ @{author_handle} に返信完了！ → {normalized_uri}")
                print(f"💾 URI保存成功 → 合計: {len(replied)} 件")
                print(f"📁 最新URI一覧（正規化済み）: {list(replied)[-5:]}")
            else:
                print(f"⚠️ 正規化されたURIが無効 → {notification_uri}")

            reply_count += 1
            time.sleep(REPLY_INTERVAL)

        except Exception as e:
            print(f"⚠️ 投稿失敗: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    print("🤖 Reply Bot 起動中…")
    run_reply_bot()