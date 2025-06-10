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
        # ログを簡略化
        # print(f"DEBUG: Checking mutual follow for {handle}")
        their_follows = client.app.bsky.graph.get_follows(params={"actor": handle, "limit": 100})
        their_following = {f.handle for f in their_follows.follows} # setにして高速化
        my_follows = client.app.bsky.graph.get_follows(params={"actor": os.environ.get("HANDLE"), "limit": 100})
        my_following = {f.handle for f in my_follows.follows} # setにして高速化
        return os.environ.get("HANDLE") in their_following and handle in my_following
    except Exception as e:
        print(f"⚠️ 相互フォロー判定エラー: {e}")
        return False

def download_image_from_blob(cid, client, did=None): # repoをdidに修正
    # CDNを試す（みつきが教えてくれたDIDを含むURLパターンと、feed_thumbnailも追加！）
    cdn_urls = []
    if did: # DIDがある場合のみDIDを含むURLを生成
        cdn_urls.extend([
            f"https://cdn.bsky.app/img/feed_thumbnail/plain/{did}/{cid}@jpeg", # サムネイルサイズ DIDあり
            f"https://cdn.bsky.app/img/feed_full/plain/{did}/{cid}@jpeg", # フルサイズ DIDあり
            f"https://cdn.bsky.app/img/feed_full/plain/{did}/{cid}", # フルサイズ DIDあり (拡張子なし)
            f"https://cdn.bsky.app/img/feed/plain/{did}/{cid}@jpeg", # feedサイズ DIDあり
            f"https://cdn.bsky.app/img/feed/plain/{did}/{cid}", # feedサイズ DIDあり (拡張子なし)
            f"https://cdn.bsky.app/blob/{did}/{cid}", # blobエンドポイント DIDあり
        ])
    # DIDがない場合や、念のため従来のパターンも試す（優先度は低くする）
    cdn_urls.extend([
        f"https://cdn.bsky.app/img/feed_thumbnail/plain/{cid}@jpeg", # サムネイルサイズ DIDなし
        f"https://cdn.bsky.app/img/feed_full/plain/{cid}@jpeg", # フルサイズ DIDなし
        f"https://cdn.bsky.app/img/feed_full/plain/{cid}", # フルサイズ DIDなし (拡張子なし)
        f"https://cdn.bsky.app/img/feed/plain/{cid}@jpeg", # feedサイズ DIDなし
        f"https://cdn.bsky.app/img/feed/plain/{cid}", # feedサイズ DIDなし (拡張子なし)
        f"https://cdn.bsky.app/blob/{cid}", # blobエンドポイント DIDなし
    ])
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }
    
    for url in cdn_urls:
        print(f"DEBUG: Trying CDN URL: {url}") # ログを簡略化
        try:
            response = requests.get(url, stream=True, timeout=10, headers=headers)
            response.raise_for_status()
            print("✅ CDN画像取得成功！")
            return Image.open(BytesIO(response.content))
        except requests.exceptions.RequestException as e:
            print(f"⚠️ CDN画像取得失敗 ({url.split('?')[0]}): {e}") # URLを簡略化
        except Exception as e:
            print(f"⚠️ CDN画像取得失敗 (予期せぬエラー): {e}") # URL削除
    
    print("❌ 全CDNパターンで画像取得失敗")
    
    # CDN失敗時、Bluesky APIでBlobを直接取得（チャッピー&Grokくんの提案！）
    if client and did: # did引数を使用
        try:
            print(f"DEBUG: Attempting to fetch blob via com.atproto.repo.getBlob for CID: {cid}, DID: {did}") # ログを簡略化
            headers = {
                'Authorization': f'Bearer {client.auth.access_token}', # 認証トークン
                'Content-Type': 'application/json' # これはいらないかもだけど念のため
            }
            params = {
                'did': did,
                'cid': cid
            }
            # requestsを使って直接APIを叩く！
            response = requests.get('https://bsky.social/xrpc/com.atproto.repo.getBlob', headers=headers, params=params, stream=True, timeout=10)
            response.raise_for_status() # HTTPエラーがあれば例外を発生させる
            print("✅ Blob API画像取得成功！")
            return Image.open(BytesIO(response.content))
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Blob API画像取得失敗 (CID: {cid}, DID: {did}): {e}")
        except Exception as e:
            print(f"⚠️ Blob API画像取得失敗 (予期せぬエラー): {e}")
    
    return None

def process_image(image_data, text="", client=None, post=None):
    if not hasattr(image_data, 'image') or not hasattr(image_data.image, 'ref') or not hasattr(image_data.image.ref, 'link'):
        print("⚠️ 画像CIDが見つかりません (image_dataの構造が不正)")
        return False

    cid = image_data.image.ref.link
    # print(f"DEBUG: CID={cid}") # ログを簡略化

    try:
        # postオブジェクトからauthorのDIDを取得してdownload_image_from_blobに渡す
        # postはThreadViewPostの場合があるので、post.postを確認
        author_did = post.post.author.did if post and hasattr(post, 'post') and hasattr(post.post, 'author') and hasattr(post.post.author, 'did') else None
        
        img = download_image_from_blob(cid, client, did=author_did) # did引数を渡す
        if img is None:
            print("⚠️ 画像取得失敗")
            return False

        # 画像の色判定
        img = img.resize((50, 50))
        colors = img.getdata()
        color_counts = Counter(colors)
        common_colors = color_counts.most_common(5)

        fluffy_count = 0
        for color in common_colors:
            r, g, b = color[0][:3]
            # ふわもこ判定を少し甘くする（例: 明るい色、暖色系）
            if (r > 180 and g > 180 and b > 180) or \
               (r > 180 and g < 180 and b < 180) or \
               (r > 180 and g > 180 and b < 180) or \
               (r > 150 and g > 100 and b < 100) or \
               (r > 150 and g < 100 and b > 100): # 新しいふわもこ色パターン追加
                fluffy_count += 1
        if fluffy_count >= 1:
            print("🎉 ふわもこ色検出！")
            return True

        # テキストキーワード判定
        check_text = text.lower()
        keywords = ["ふわふわ", "もこもこ", "かわいい", "fluffy", "cute", "soft", "もふもふ", "愛しい", "癒し", "たまらん", "adorable"] # キーワード追加
        if any(keyword in check_text for keyword in keywords):
            print("🎉 キーワード検出！")
            return True

        return False
    except Exception as e:
        print(f"🔍 画像解析エラー: {e}") # DEBUG削除、簡略化
        return False

def is_quoted_repost(post):
    try:
        # postがThreadViewPostの場合、post.postに実際の投稿オブジェクトが入っている
        actual_post_record = post.post.record if hasattr(post, 'post') else post.record

        if hasattr(actual_post_record, 'embed') and actual_post_record.embed:
            embed = actual_post_record.embed
            # recordWithMediaの場合も考慮
            if hasattr(embed, 'record') and embed.record:
                print(f"📌 引用リポスト検出: URI={embed.record.uri}") # ログを簡略化
                return True
            # recordWithMediaの場合のrecordも確認
            elif hasattr(embed, 'record') and hasattr(embed.record, 'record') and embed.record.record:
                print(f"📌 引用リポスト検出 (RecordWithMedia内): URI={embed.record.record.uri}")
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
                print(f"✅ 読み込んだ reposted_uris: {len(uris)}件") # ログを簡略化
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
        return "ja" # デフォルトは日本語
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
            # collection/rkey 部分のみを正規化
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
            # 履歴サンプルはログが多くなるので削除
            # if fuwamoko_uris:
            #     print(f"📜 履歴サンプル: {list(fuwamoko_uris.keys())[:5]}")
        except Exception as e:
            print(f"⚠️ 履歴読み込みエラー: {e}")
    else:
        print(f"📂 {FUWAMOKO_FILE} が見つかりません。新規作成します")
        with open(FUWAMOKO_FILE, 'w', encoding='utf-8') as f:
            pass

def save_fuwamoko_uri(uri):
    normalized_uri = normalize_uri(uri)
    # 1日1回制限を24時間にする
    if normalized_uri in fuwamoko_uris and (datetime.now(timezone.utc) - fuwamoko_uris[normalized_uri]).total_seconds() < 24 * 3600:
        print(f"⩗ 履歴保存スキップ（24時間以内）: {normalized_uri.split('/')[-1]}") # URIを簡略化
        return
    try:
        with open(FUWAMOKO_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{normalized_uri}|{datetime.now(timezone.utc).isoformat()}\n")
        fuwamoko_uris[normalized_uri] = datetime.now(timezone.utc)
        print(f"💾 履歴保存: {normalized_uri.split('/')[-1]}") # URIを簡略化
    except Exception as e:
        print(f"⚠️ 履歴保存エラー: {e}")

def load_session_string():
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, 'r', encoding='utf-8') as f:
                session_str = f.read().strip()
                print(f"✅ セッション文字列読み込み") # ログを簡略化
                return session_str
        except Exception as e:
            print(f"⚠️ セッション文字列読み込みエラー: {e}")
    return None

def save_session_string(session_str):
    try:
        with open(SESSION_FILE, 'w', encoding='utf-8') as f:
            f.write(session_str)
        print(f"💾 セッション文字列保存") # ログを簡略化
    except Exception as e:
        print(f"⚠️ セッション文字列保存エラー: {e}")

def process_post(post, client, fuwamoko_uris, reposted_uris):
    try:
        # postがThreadViewPostの場合、post.postに実際の投稿オブジェクトが入っている
        actual_post = post.post if hasattr(post, 'post') else post
        
        # ログを簡略化
        # print(f"DEBUG: Processing Post indexed_at={actual_post.indexed_at}")
        print(f"DEBUG: Processing {actual_post.author.handle}'s post (URI: {actual_post.uri.split('/')[-1]})") # URIを短くする
        
        if str(actual_post.uri) in fuwamoko_uris or \
           actual_post.author.handle == HANDLE or \
           is_quoted_repost(post) or \
           str(actual_post.uri).split('/')[-1] in reposted_uris:
            print(f"DEBUG: Skipping post {actual_post.uri.split('/')[-1]} (already processed, own post, quoted repost, or reposted).") # URIを短くする
            return False

        # ログが多くなるのでPost JSONとThread JSONの出力は一旦コメントアウト
        # post_dict = {
        #     "uri": actual_post.uri,
        #     "cid": actual_post.cid,
        #     "author": actual_post.author.handle,
        #     "did": actual_post.author.did,
        #     "text": getattr(actual_post.record, "text", ""),
        #     "embed": getattr(actual_post.record, "embed", None).__dict__ if getattr(actual_post.record, "embed", None) else None
        # }
        # print(f"🔍 DEBUG: Post JSON={json.dumps(post_dict, default=str, ensure_ascii=False, indent=2)}")

        # thread_responseから取得したpostオブジェクトを直接process_imageに渡すように修正
        # ここではThreadViewPostの形を想定
        # thread_response = client.app.bsky.feed.get_post_thread(params={"uri": actual_post.uri, "depth": 2})
        # thread_dict = {
        #     "uri": thread_response.thread.post.uri,
        #     "post": {
        #         "author": thread_response.thread.post.author.handle,
        #         "did": thread_response.thread.post.author.did,
        #         "text": getattr(thread_response.thread.post.record, "text", ""),
        #         "embed": getattr(thread_response.thread.post.record, "embed", None).__dict__ if getattr(thread_response.thread.post.record, "embed", None) else None
        #     }
        # }
        # print(f"🔍 DEBUG: Thread JSON={json.dumps(thread_dict, default=str, ensure_ascii=False, indent=2)}")


        text = getattr(actual_post.record, "text", "")
        uri = str(actual_post.uri)
        post_id = uri.split('/')[-1]
        author = actual_post.author.handle
        embed = getattr(actual_post.record, "embed", None)

        image_data_list = []
        if embed and hasattr(embed, 'images') and embed.images:
            # print("🔍 DEBUG: Found direct embedded images") # ログを簡略化
            image_data_list = embed.images
            # print(f"🔍 DEBUG: Direct images={[{k: getattr(img, k) for k in ['alt', 'image']} for img in image_data_list]}") # ログを簡略化
        elif embed and hasattr(embed, 'record') and hasattr(embed.record, 'embed') and hasattr(embed.record.embed, 'images') and embed.record.embed.images:
            # print("🔍 DEBUG: Found embedded images in quoted post") # ログを簡略化
            image_data_list = embed.record.embed.images
            # print(f"🔍 DEBUG: Quoted post author={embed.record.author.handle}, DID={embed.record.author.did}") # ログを簡略化
            # print(f"🔍 DEBUG: Quoted images={[{k: getattr(img, k) for k in ['alt', 'image']} for img in image_data_list]}") # ログを簡略化
        elif embed and embed.get('$type') == 'app.bsky.embed.recordWithMedia':
            # print("🔍 DEBUG: Found recordWithMedia embed") # ログを簡略化
            if hasattr(embed, 'media') and hasattr(embed.media, 'images') and embed.media.images:
                image_data_list = embed.media.images
                # print(f"🔍 DEBUG: RecordWithMedia images={[{k: getattr(img, k) for k in ['alt', 'image']} for img in image_data_list]}") # ログを簡略化
        else:
            # print("🔍 DEBUG: No images found in post after embed check.") # ログを簡略化
            return False

        if not is_mutual_follow(client, author):
            print(f"DEBUG: Skipping post from {author} (not mutual follow).") # ログを簡略化
            return False

        if image_data_list:
            image_data = image_data_list[0]
            # print(f"🔍 DEBUG: image_data={image_data.__dict__}") # ログを簡略化
            # print(f"🔍 DEBUG: image_data keys={list(image_data.__dict__.keys())}") # ログを簡略化
            
            if not getattr(image_data, 'alt', '').strip():
                print("DEBUG: Image alt text is empty. Considering it for 'ふわもこ' analysis based on colors.")
            
            # process_imageに元のpostオブジェクト（ThreadViewPost or PostView）を渡す
            # process_image内でpost.post.author.didにアクセスできるように
            if process_image(image_data, text, client=client, post=post) and random.random() < 0.5: # 50%の確率で返信する
                lang = detect_language(client, author)
                reply_text = open_calm_reply("", text, lang=lang)
                print(f"✨ ふわもこ共感成功 → @{author}: {text} (言語: {lang})") # ログを簡略化

                reply_ref = AppBskyFeedPost.ReplyRef(
                    root={"$type": "com.atproto.repo.strongRef", "uri": uri, "cid": actual_post.cid}, # cidはactual_post.cidを使う
                    parent={"$type": "com.atproto.repo.strongRef", "uri": uri, "cid": actual_post.cid} # cidはactual_post.cidを使う
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
                return True
            else:
                print(f"🚫 ふわもこ要素なしまたは確率外 → @{author} (URI: {actual_post.uri.split('/')[-1]})") # URIを短くする
        else:
            print(f"DEBUG: No image_data_list to process for post {uri.split('/')[-1]}.") # URIを短くする
        
        return False
    except Exception as e:
        print(f"⚠️ 投稿処理エラー (URI: {post.post.uri.split('/')[-1] if hasattr(post, 'post') else post.uri.split('/')[-1]}): {e}") # URIを短くする
        return False

def run_once():
    try:
        client = Client()
        session_str = load_session_string()
        if session_str:
            client.login(session_string=session_str)
            print(f"📨💖 ふわもこ共感Bot起動！ セッション再利用") # ログを簡略化
        else:
            client.login(login=HANDLE, password=APP_PASSWORD)
            session_str = client.export_session_string()
            save_session_string(session_str)
            print(f"📨💖 ふわもこ共感Bot起動！ 新規セッション") # ログを簡略化

        load_fuwamoko_uris()
        reposted_uris = load_reposted_uris_for_check()

        # 特定投稿を優先処理
        target_post_uri = "at://did:plc:lmntwwwhxvedq3r4retqishb/app.bsky.feed.post/3lr6hwd3a2c2k"
        try:
            print(f"🔍 DEBUG: Attempting to get specific post thread for URI: {target_post_uri.split('/')[-1]}") # URIを短くする
            thread_response = client.app.bsky.feed.get_post_thread(params={"uri": target_post_uri, "depth": 2})
            # ここではThreadViewPostオブジェクト (thread_response.thread) をそのままprocess_postに渡す
            if process_post(thread_response.thread, client, fuwamoko_uris, reposted_uris):
                print(f"✅ 特定投稿処理成功: {target_post_uri.split('/')[-1]}") # URIを短くする
            else:
                print(f"DEBUG: 特定投稿処理スキップまたは失敗: {target_post_uri.split('/')[-1]}") # URIを短くする
        except Exception as e:
            print(f"⚠️ Specific get_post_threadエラー: {e}")

        # タイムライン処理
        timeline = client.app.bsky.feed.get_timeline(params={"limit": 50})
        feed = timeline.feed

        for post in sorted(feed, key=lambda x: x.post.indexed_at, reverse=True):
            time.sleep(random.uniform(2, 5))
            process_post(post, client, fuwamoko_uris, reposted_uris)

    except InvokeTimeoutError:
        print("⚠️ APIタイムアウト！")
    except Exception as e:
        print(f"⚠️ ログインまたは実行エラー: {e}")

if __name__ == "__main__":
    load_dotenv()
    run_once()
