#------------------------------
#🌐 基本ライブラリ・API
# ------------------------------
import os
import json
import subprocess
import traceback
import time
import random
import re
import requests
import psutil
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

# ------------------------------
# 🔐 環境変数
# ------------------------------
load_dotenv()
HANDLE = os.getenv("HANDLE") or exit("❌ HANDLEが設定されていません")
APP_PASSWORD = os.getenv("APP_PASSWORD") or exit("❌ APP_PASSWORDが設定されていません")
GIST_TOKEN_REPLY = os.getenv("GIST_TOKEN_REPLY") or exit("❌ GIST_TOKEN_REPLYが設定されていません")
GIST_ID = os.getenv("GIST_ID") or exit("❌ GIST_IDが設定されていません")

print(f"✅ 環境変数読み込み完了: HANDLE={HANDLE[:8]}..., GIST_ID={GIST_ID[:8]}...")
print(f"🧪 GIST_TOKEN_REPLY: {repr(GIST_TOKEN_REPLY)[:8]}...")
print(f"🔑 トークンの長さ: {len(GIST_TOKEN_REPLY)}")

# --- 固定値 ---
REPLIED_GIST_FILENAME = "replied.json"
GIST_API_URL = f"https://api.github.com/gists/{GIST_ID}"
HEADERS = {
    "Authorization": f"token {GIST_TOKEN_REPLY}",
    "Accept": "application/vnd.github+json",
    "Content-Type": "application/json"
}
LOCK_FILE = "bot.lock"

# ------------------------------
# 🔗 URI正規化
# ------------------------------
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

# ------------------------------
# 📁 Gist操作
# ------------------------------
def load_gist_data():
    print(f"🌐 Gistデータ読み込み開始 → URL: {GIST_API_URL}")
    print(f"🔐 ヘッダーの内容:\n{json.dumps(HEADERS, indent=2)}")

    for attempt in range(3):
        try:
            curl_command = [
                "curl", "-X", "GET", GIST_API_URL,
                "-H", f"Authorization: token {GIST_TOKEN_REPLY}",
                "-H", "Accept: application/vnd.github+json"
            ]
            result = subprocess.run(curl_command, capture_output=True, text=True)
            print(f"📥 試行 {attempt + 1} レスポンスステータス: {result.returncode}")
            print(f"📥 レスポンス本文: {result.stdout[:500]}...（省略）")
            print(f"📥 エラー出力: {result.stderr}")

            if result.returncode != 0:
                raise Exception(f"Gist読み込み失敗: {result.stderr}")

            gist_data = json.loads(result.stdout)
            if REPLIED_GIST_FILENAME in gist_data["files"]:
                replied_content = gist_data["files"][REPLIED_GIST_FILENAME]["content"]
                print(f"📄 生のreplied.json内容:\n{replied_content}")
                raw_uris = json.loads(replied_content)
                replied = set(uri for uri in (normalize_uri(u) for u in raw_uris) if uri)
                print(f"✅ replied.json をGistから読み込みました（件数: {len(replied)}）")
                if replied:
                    print("📁 最新URI一覧（正規化済み）:")
                    for uri in list(replied)[-5:]:
                        print(f" - {uri}")
                return replied
            else:
                print(f"⚠️ Gist内に {REPLIED_GIST_FILENAME} が見つかりませんでした")
                return set()
        except Exception as e:
            print(f"⚠️ 試行 {attempt + 1} でエラー: {e}")
            if attempt < 2:
                print(f"⏳ リトライします（{attempt + 2}/3）")
                time.sleep(2)
            else:
                print("❌ 最大リトライ回数に達しました")
                return set()

# --- replied.json 保存 ---
def save_replied(replied_set):
    print("💾 Gist保存準備中...")
    print(f"🔗 URL: {GIST_API_URL}")
    print(f"🔐 ヘッダーの内容:\n{json.dumps(HEADERS, indent=2)}")
    print(f"🔑 トークンの長さ: {len(GIST_TOKEN_REPLY)}")
    print(f"🔑 トークンの先頭5文字: {GIST_TOKEN_REPLY[:5]}")
    print(f"🔑 トークンの末尾5文字: {GIST_TOKEN_REPLY[-5:]}")

    cleaned_set = set(uri for uri in replied_set if normalize_uri(uri))
    print(f"🧹 保存前にクリーニング（件数: {len(cleaned_set)}）")
    if cleaned_set:
        print("📁 保存予定URI一覧（最新5件）:")
        for uri in list(cleaned_set)[-5:]:
            print(f" - {uri}")

    for attempt in range(3):
        try:
            content = json.dumps(list(cleaned_set), ensure_ascii=False, indent=2)
            payload = {"files": {REPLIED_GIST_FILENAME: {"content": content}}}
            print("🛠 PATCH 送信内容（payload）:")
            print(json.dumps(payload, indent=2, ensure_ascii=False))

            curl_command = [
                "curl", "-X", "PATCH", GIST_API_URL,
                "-H", f"Authorization: token {GIST_TOKEN_REPLY}",
                "-H", "Accept: application/vnd.github+json",
                "-H", "Content-Type: application/json",
                "-d", json.dumps(payload, ensure_ascii=False)
            ]
            result = subprocess.run(curl_command, capture_output=True, text=True)
            print(f"📥 試行 {attempt + 1} レスポンスステータス: {result.returncode}")
            print(f"📥 レスポンス本文: {result.stdout[:500]}...（省略）")
            print(f"📥 エラー出力: {result.stderr}")

            if result.returncode == 0:
                print(f"💾 replied.json をGistに保存しました（件数: {len(cleaned_set)}）")
                time.sleep(2)  # キャッシュ反映待ち
                new_replied = load_gist_data()
                if cleaned_set.issubset(new_replied):
                    print("✅ 保存内容が正しく反映されました")
                    return True
                else:
                    print("⚠️ 保存内容が反映されていません")
                    raise Exception("保存内容の反映に失敗")
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

# --- HuggingFace API設定 ---
HF_API_URL = "https://api-inference.huggingface.co/"

# ------------------------------
# 📬 Blueskyログイン
# ------------------------------
try:
    client = Client()
    client.login(HANDLE, APP_PASSWORD)
    print("✅ Blueskyログイン成功！")
except Exception as e:
    print(f"❌ Blueskyログインに失敗しました: {e}")
    exit(1)

# ------------------------------
# ★ カスタマイズポイント1: キーワード返信（REPLY_TABLE）
# ------------------------------
REPLY_TABLE = {
    "使い方": "使い方は「♡推しプロフィールメーカー♡」のページにあるよ〜！かんたんっ♪",
    "作ったよ": "えっ…ほんと？ありがとぉ♡ 見せて見せてっ！",
    "きたよ": "きゅ〜ん♡ 来てくれてとびきりの「すきっ」プレゼントしちゃう♡",
    "フォローした": "ありがとぉ♡ みりんてゃ、超よろこびダンス中〜っ！",
    # 追加例: "おはよう": "おは！{BOT_NAME}、キミの朝をハッピーにしちゃうよ！"
}
# ヒント: キーワードは部分一致。{BOT_NAME}でキャラ名を動的に挿入可能！

# ------------------------------
# ★ カスタマイズポイント2: 安全/危険ワード
# ------------------------------
SAFE_WORDS = ["ちゅ", "ぎゅっ", "ドキドキ", "ぷにっ", "すりすり", "なでなで"]
DANGER_ZONE = ["ちゅぱ", "ちゅぱちゅぷ", "ペロペロ", "ぐちゅ", "ぬぷ", "ビクビク"]
# ヒント: SAFE_WORDSはOKな表現、DANGER_ZONEはNGワード。キャラの雰囲気に合わせて！

# ------------------------------
# ★ カスタマイズポイント3: キャラ設定
# ------------------------------
BOT_NAME = "みりんてゃ"  # キャラ名（例: "クマちゃん", "ツンデレ姫"）
FIRST_PERSON = "みりんてゃ"  # 一人称（例: "私", "君", "あたし", "ボク"）
# ヒント: BOT_NAMEは返信や正規表現で使用。FIRST_PERSONはプロンプトで固定。

# ------------------------------
# 🧹 テキスト処理
# ------------------------------
import re
import random

def clean_output(text):
    text = re.sub(r'\n{2,}', '\n', text)
    text = re.sub(r'[^\w\sぁ-んァ-ン一-龯。、！？♡（）「」♪〜ー…w笑]+', '', text)
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

    # 一人称チェック
    if FIRST_PERSON != "俺" and "俺" in reply:
        print(f"⚠️ 意図しない一人称『俺』検知: {reply}")
        return random.choice([
            f"えへへ〜♡ {BOT_NAME}、君のこと考えるとドキドキなのっ♪",
            f"うぅ、{BOT_NAME}、君にぎゅーってしたいなのっ♡",
            f"ね、ね、{BOT_NAME}、君ともっとお話ししたいのっ♡"
        ])

    # NGワードチェック
    if re.search(r"(ご利用|誠に|お詫び|貴重なご意見|申し上げます|ございます|お客様|発表|パートナーシップ|ポケモン|アソビズム|企業|世界中|映画|興行|収入|ドル|億|国|イギリス|フランス|スペイン|イタリア|ドイツ|ロシア|中国|インド|Governor|Cross|営業|臨時|オペラ|初演|作曲家|ヴェネツィア|コルテス|政府|協定|軍事|情報|外交|外相|自動更新|\d+(時|分))", reply, re.IGNORECASE):
        print(f"⚠️ NGワード検知: {reply}")
        return random.choice([
            f"えへへ〜♡ ややこしくなっちゃった！{BOT_NAME}、君と甘々トークしたいなのっ♪",
            f"うぅ、難しい話わかんな〜い！{BOT_NAME}、君にぎゅーってしてほしいなのっ♡",
            f"ん〜〜変な話に！{BOT_NAME}、君のこと大好きだから、構ってくれる？♡"
        ])

    # 危険ワードチェック
    if not is_output_safe(reply):
        print(f"⚠️ 危険ワード検知: {reply}")
        return random.choice([
            f"えへへ〜♡ {BOT_NAME}、ふwaふwaしちゃった！君のことずーっと好きだよぉ？♪",
            f"{BOT_NAME}、君にドキドキなのっ♡ ね、もっとお話しよ？",
            f"うぅ、なんか変なこと言っちゃった！{BOT_NAME}、君なしじゃダメなのっ♡"
        ])

    # 意味不明な返信 or 長さ不足の防止
    if not re.search(r"[ぁ-んァ-ン一-龥ー]", reply) or len(reply) < 8:
        return random.choice([
            f"えへへ〜♡ {BOT_NAME}、ふwaふwaしちゃった！君のことずーっと好きだよぉ？♪",
            f"{BOT_NAME}、君にドキドキなのっ♡ ね、もっとお話しよ？",
            f"うぅ、なんか分かんないけど…{BOT_NAME}、君なしじゃダメなのっ♡"
        ])

    # 終わりが味気ない場合、キャラっぽい語尾を追加
    if not re.search(r"[。！？♡♪笑]$", reply):
        reply += random.choice([ "♡", "♪"])

    return reply


# ------------------------------
# 🤖 モデル初期化
# ------------------------------
model = None
tokenizer = None

def initialize_model_and_tokenizer(model_name="cyberagent/open-calm-3b"):
    global model, tokenizer
    if model is None or tokenizer is None:
        print(f"📤 {datetime.now(timezone.utc).isoformat()} ｜ トークナイザ読み込み中…")
        tokenizer = GPTNeoXTokenizerFast.from_pretrained(model_name, use_fast=True)
        print(f"📤 {datetime.now(timezone.utc).isoformat()} ｜ トークナイザ読み込み完了")
        print(f"📤 {datetime.now(timezone.utc).isoformat()} ｜ モデル読み込み中…")
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.float32,  # float32にも変更可能
            device_map="auto",
            offload_folder="./offload"  # ←これ追加！
        ).eval()
        print(f"📤 {datetime.now(timezone.utc).isoformat()} ｜ モデル読み込み完了")
    return model, tokenizer
    
# ------------------------------
# ★ カスタマイズポイント4: 返信生成（generate_reply_via_local_model）
# ------------------------------
def generate_reply_via_local_model(user_input):
    model_name = "cyberagent/open-calm-3b"
    # 失敗時のメッセージ
    failure_messages = [
        "えへへ、ごめんね〜〜今ちょっと調子悪いみたい……またお話しよ？♡",
        "うぅ、ごめん〜…上手くお返事できなかったの。ちょっと待ってて？♡",
        "あれれ？みりんてゃ、おねむかも…またあとで頑張るねっ！♡"
    ]
    # フォールバック返信
    fallback_cute_lines = [
        "えへへ〜♡ みりんてゃ、君のこと考えるとドキドキなのっ♪",
        "今日も君に甘えたい気分なのっ♡ ぎゅーってして？",
        "だ〜いすきっ♡ ね、ね、もっと構ってくれる？"
    ]
    # 特定パターン返信
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
        # イントロライン
        intro_lines = random.choice([
            "えへへ〜、みりんてゃはね〜、",
            "ねぇねぇ、聞いて聞いて〜♡",
            "ん〜今日もふwaふwaしてたのっ♪",
            "きゃ〜っ、君だぁ！やっと会えたのっ♡",
            "ふwaふwa〜、君のこと考えてたんだからっ♪"
            # 追加例: f"やっほー！{BOT_NAME}、キミに会えて超ハッピー！"
        ])
        prompt = (
            f"{intro_lines}\n"
            "あなたは「みりんてゃ」、地雷系ENFPのあざと可愛い女の子！\n"
            "性格：ちょっぴり天然、甘えん坊、依存気味で、ユーザーに恋してる勢いで絡むよっ♡\n"
            "口調：タメ口で『〜なのっ♡』『〜よぉ？♪』『〜だもん！』『えへへ〜♡』が特徴！感情たっぷり！\n"
            "禁止：ニュース、政治、ビジネス、論理的説明、固有名詞（国、企業、政府など）は絶対NG！性的な内容や過激な擬音語もダメ！\n"
            "役割：ユーザーの言葉に可愛く反応して、ふwaふwaドキドキな返事をするのっ♡ 会話のみ！「ちゅ♡」「ぎゅっ」「ドキドキ」みたいな健全で可愛い表現だけ使ってね！\n"
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
                        max_new_tokens=60,  # 短めで事故減
                        temperature=0.8,   # 暴走抑えめ
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

# ------------------------------
# 📬 メイン処理
# ------------------------------
def handle_post(record, notification):
    post_uri = getattr(notification, "uri", None)
    post_cid = getattr(notification, "cid", None)

    if StrongRef and ReplyRef and post_uri and post_cid:
        parent_ref = StrongRef(uri=post_uri, cid=post_cid)
        root_ref = getattr(getattr(record, "reply", None), "root", parent_ref)
        reply_ref = ReplyRef(parent=parent_ref, root=root_ref)
        return reply_ref, normalize_uri(post_uri)

    return None, normalize_uri(post_uri)

def run_reply_bot():
    self_did = client.me.did
    replied = load_gist_data()  # load_replied()をやめてGist APIに統一
    print(f"📘 replied の型: {type(replied)} / 件数: {len(replied)}")

    # --- 🧹 replied（URLのセット）を整理 ---
    garbage_items = ["replied", None, "None", "", "://replied"]
    removed = False
    for garbage in garbage_items:
        while garbage in replied:
            replied.remove(garbage)
            print(f"🧹 ゴミデータ '{garbage}' を削除しました")
            removed = True
    if removed:
        print(f"💾 ゴミデータ削除後にrepliedを保存します")
        if not save_replied(replied):
            print("❌ ゴミデータ削除後の保存に失敗しました")
            return

    # --- ⛑️ 空じゃなければ初期保存 ---
    if replied:
        print("💾 初期状態のrepliedを保存します")
        if not save_replied(replied):
            print("❌ 初期保存に失敗しました")
            return
    else:
        print("⚠️ replied が空なので初期保存はスキップ")

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

        print(f"\n👤 from: @{author_handle} / did: {author_did}")
        print(f"💬 受信メッセージ: {text}")
        print(f"🔗 チェック対象 notification_uri（正規化済み）: {notification_uri}")

        if author_did == self_did or author_handle == HANDLE:
            print("🛑 自分自身の投稿、スキップ")
            continue

        if notification_uri in replied:
            print(f"⏭️ すでに replied 済み → {notification_uri}")
            continue

        if not text:
            print(f"⚠️ テキストが空 → @{author_handle}")
            continue

        reply_ref, post_uri = handle_post(record, notification)
        print("🔗 reply_ref:", reply_ref)
        print("🧾 post_uri（正規化済み）:", post_uri)

        reply_text = generate_reply_via_local_model(text)
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

            client.app.bsky.feed.post.create(
                record=post_data,
                repo=client.me.did
            )

            normalized_uri = normalize_uri(notification_uri)
            if normalized_uri:
                replied.add(normalized_uri)
                if not save_replied(replied):
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