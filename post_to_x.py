import os
import re
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import List, Optional

# --- 設定 ---
TARGET_REPO = "CANDY-HOUSE/.github"
TARGET_FILE = "changelog.html"
# GitHub Actionsでは自動で設定されるトークンを使用。ローカル実行時は環境変数に入れてください。
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# 正規表現のプリコンパイル（高速化）
RE_HTML_TAGS = re.compile(r'<[^>]*>')
RE_DIFF_PREFIX = re.compile(r'^[+\-]')

def create_gh_session() -> requests.Session:
    """GitHub API用の最適化されたセッションを作成"""
    session = requests.Session()
    
    # 認証ヘッダーの設定
    session.headers.update({
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "GitHub-Actions-Changelog-Fetcher"
    })
    if GITHUB_TOKEN:
        session.headers["Authorization"] = f"token {GITHUB_TOKEN}"

    # リトライ戦略の設定（安定性の向上）
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    return session

def fetch_changelog_diff(base: str, head: str) -> List[str]:
    """
    指定されたコミット間の差分を取得し、クリーニングされたリストを返す。
    """
    url = f"https://api.github.com/repos/{TARGET_REPO}/compare/{base}...{head}"
    session = create_gh_session()
    
    try:
        # タイムアウトを設定してハングを防止
        response = session.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        files = data.get("files", [])
        target_patch = next((f.get("patch", "") for f in files if f["filename"] == TARGET_FILE), None)

        if not target_patch:
            return [f"{TARGET_FILE} に実質的な変更はありませんでした。"]

        return process_diff_patch(target_patch)

    except requests.exceptions.RequestException as e:
        return [f"Error: API通信に失敗しました ({str(e)})"]
    except Exception as e:
        return [f"Error: 予期しないエラーが発生しました ({str(e)})"]

def process_diff_patch(patch_text: str) -> List[str]:
    """
    diffのpatchテキストから、タグを除去し、意味のある変更行のみを抽出する。
    """
    cleaned_lines = []
    
    for line in patch_text.splitlines():
        # diffのメタデータ行（+++や---）を除外
        if line.startswith("+++") or line.startswith("---"):
            continue
            
        # 追加(+)または削除(-)の行のみ処理
        if line.startswith(("+", "-")):
            # 1. 差分記号を除去したテキストを作成
            content = line[1:].strip()
            
            # 2. HTMLタグを除去
            plain_text = RE_HTML_TAGS.sub('', content).strip()
            
            # 3. タグ除去後に文字が残っている場合のみ採用
            if plain_text:
                # 差分記号を保持した状態でリストに追加
                prefix = line[0]
                cleaned_lines.append(f"{prefix} {plain_text}")
                
    return cleaned_lines if cleaned_lines else ["変更はありましたが、有効なテキスト差分は見つかりませんでした。"]


from typing import List

# --- 定数 ---
CHARACTER_LIMIT = 280
CHANGELOG_URL = "jp.candyhouse.co/pages/changelog"
# TwitterのURL短縮（t.co）を考慮した固定文字数（JSのコードに合わせた23文字）
TWITTER_URL_WEIGHT = 23
ELLIPSIS = "…"

def get_text_weight(text: str) -> int:
    """
    半角記号・英数（ASCII 32-126）を1、それ以外（全角等）を2としてカウントする。
    """
    weight = 0
    for char in text:
        # JSの [ -~] (SpaceからTildeまで) に相当する判定
        if 32 <= ord(char) <= 126:
            weight += 1
        else:
            weight += 2
    return weight

def truncate_text(text: str, limit: int) -> str:
    """
    制限文字数（weight）に収まるように文字列を切り詰め、末尾に三点リーダーを付与する。
    """
    ellipsis_w = get_text_weight(ELLIPSIS)
    current_w = 0
    truncated = ""
    
    for char in text:
        char_w = get_text_weight(char)
        if current_w + char_w > (limit - ellipsis_w):
            break
        truncated += char
        current_w += char_w
        
    return truncated + ELLIPSIS

def format_changelog_tweets(lines: List[str]) -> List[str]:
    """
    変更点リストを受け取り、280文字制限に合わせたツイート配列を作成する。
    """
    tweets = []
    current_buffer = ""

    for line in lines:
        line_weight = get_text_weight(line)

        if current_buffer:
            # すでにバッファがある場合、改行を含めて追加できるかチェック
            if get_text_weight(current_buffer) + line_weight + 1 <= CHARACTER_LIMIT:
                current_buffer += f"\n{line}"
                continue
            else:
                # 入らない場合は現在のバッファを確定
                tweets.append(current_buffer)
                current_buffer = ""

        # 新規またはバッファが空の状態での処理
        if line_weight > CHARACTER_LIMIT:
            # 1行で制限を超える場合は、その場で切り詰めて即座に確定
            tweets.append(truncate_text(line, CHARACTER_LIMIT))
        else:
            current_buffer = line

    # 最後のバッファとURLの統合処理
    if current_buffer:
        buffer_weight = get_text_weight(current_buffer)
        # URLを結合できる余裕があるか（改行1 + URL 23文字）
        if buffer_weight <= (CHARACTER_LIMIT - TWITTER_URL_WEIGHT - 1):
            tweets.append(f"{current_buffer}\n{CHANGELOG_URL}")
        else:
            # 余裕がない場合は分けて追加
            tweets.append(current_buffer)
            tweets.append(CHANGELOG_URL)
    else:
        # 万が一バッファが空で終了していた場合でもURLは追加
        if not tweets or tweets[-1] != CHANGELOG_URL:
            tweets.append(CHANGELOG_URL)

    return tweets

import os
import tweepy
from typing import List

def post_to_x(tweets: List[str]):
    """
    作成されたツイート配列をX(Twitter)に投稿する。
    複数ある場合はスレッド形式で投稿。
    """
    # # GitHub ActionsのSecretsから取得することを想定
    bearer_token = os.getenv("X_BEARER_TOKEN")
    api_key = os.getenv("X_API_KEY")
    api_secret = os.getenv("X_API_SECRET")
    access_token = os.getenv("X_ACCESS_TOKEN")
    access_token_secret = os.getenv("X_ACCESS_TOKEN_SECRET")
    
    
    # mylta
    # bearer_token = "AAAAAAAAAAAAAAAAAAAAAKzs2AEAAAAAcJFa%2BKD1Dy3eCdCWTRZgg2YqCQQ%3DgdEX4S8EvRNmAObKy2vBQDfAtFKM5MLiOpFgLRisscvUKjXOIX"
    # api_key = "uqqX01X8CXEpMAFpA6iVU4tfI"
    # api_secret = "Dn0orUOm2UvWlA1PtkPGeqKGkVcFquUhdDIDqMX5v10Ur71Ffv"
    # access_token = "1287579233552760832-NuUmYAhCX1nuxrpmvkrlXSJaIS6aIx"
    # access_token_secret = "DwvSyrd8sFPAimzpfW3oNiD5Sfn7WAuWQbLw0H4KEAZr5"
    
    # candyhouse
    # bearer_token = "AAAAAAAAAAAAAAAAAAAAABDzwgEAAAAAHLCOnOAcN4naqNY1SHJejYuYtE4%3DPsJB9Jy2RMAvBlKUqgQKeJSkCvMm79bL6V1WiEl5KYvF9sMbhf"
    # api_key = "7BNZVZOcZLEGjoq2zPxGXvbZq"
    # api_secret = "776akYx5Bv72P7tCjBw50C5sBza14BsQs8jSj6KYK3oddGouPK"
    # access_token = "1852552168253038592-vguRuh99QfTbYmyYXSwodB0RHmQxNd"
    # access_token_secret = "HZX4oHcQgpdErntwXctlnJta21pMRGIQQbM6HxqlJZ7i3"

    if not all([api_key, api_secret, access_token, access_token_secret]):
        print("Error: X APIの認証情報が不足しています。")
        return

    # クライアントの初期化 (API v2)
    client = tweepy.Client(
        bearer_token=bearer_token,
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_token_secret
    )

    last_tweet_id = None

    try:
        for i, tweet_content in enumerate(tweets):
            if i == 0:
                # 最初のツイート
                response = client.create_tweet(text=tweet_content)
            else:
                # 2枚目以降は前のツイートへの返信（スレッド化）
                response = client.create_tweet(
                    text=tweet_content,
                    in_reply_to_tweet_id=last_tweet_id
                )
            
            last_tweet_id = response.data['id']
            print(f"Tweet {i+1} posted successfully. ID: {last_tweet_id}")

    except tweepy.TweepyException as e:
        print(f"Error: Xへの投稿中にエラーが発生しました: {e}")

# --- 統合実行例 ---
if __name__ == "__main__":
    # 1. 前段のロジックで差分取得
    lines = fetch_changelog_diff("b4620a94a60597f3dc9703aaf831105297c492af", "65bcab985a3830bb7b8bf782565bc8d095cd2f8a")
    # 2. ツイート形式に変換
    tweet_list = format_changelog_tweets(lines)
    # 3. 投稿
    post_to_x(tweet_list)

# --- 実行例 ---
if __name__ == "__main__":
    diff_results = fetch_changelog_diff("b4620a94a60597f3dc9703aaf831105297c492af", "65bcab985a3830bb7b8bf782565bc8d095cd2f8a")
    for item in diff_results:
        print(item)
    result = format_changelog_tweets(diff_results)
    print("")
    print("編集済み:")
    
    for item in result:
        print(item)
        print("")
        

