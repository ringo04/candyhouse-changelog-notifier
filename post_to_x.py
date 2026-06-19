import os
import re
import time
import json
import urllib.request
import urllib.error
import tweepy
from typing import List


# --- 設定 ---
TARGET_REPO = "CANDY-HOUSE/.github"
TARGET_FILE = "changelog.html"
CHANGELOG_URL = "jp.candyhouse.co/pages/changelog"
CHARACTER_LIMIT = 280
TWITTER_URL_WEIGHT = 23
ELLIPSIS = "…"

RE_HTML_TAGS = re.compile(r'<[^>]*>')


# --- GitHub API 関連 (requestsを排除し標準ライブラリ化) ---
def fetch_changelog_diff(base: str, head: str) -> List[str]:
    if not base or not head:
        return ["Error: SHAが指定されていません。"]
    
    url = f"https://api.github.com/repos/{TARGET_REPO}/compare/{base}...{head}"
    
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "GitHub-Actions-Changelog-Fetcher"
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"

    req = urllib.request.Request(url, headers=headers)

    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode('utf-8'))
                files = data.get("files", [])
                
                patch = next((f.get("patch", "") for f in files if f["filename"] == TARGET_FILE), None)
                if not patch:
                    return []
                return process_patch(patch)
                
        except urllib.error.HTTPError as e:
            if e.code in [429, 500, 502, 503, 504]:
                time.sleep(1)
                continue
            print(f"GitHub API Error: HTTP {e.code}")
            return []
        except Exception as e:
            print(f"GitHub API Error: {e}")
            return []
    return []

def process_patch(patch_text: str) -> List[str]:
    cleaned_lines = []
    for line in patch_text.splitlines():
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---")):
            content = line[1:].strip()
            plain_text = RE_HTML_TAGS.sub('', content).strip()
            if plain_text:
                cleaned_lines.append(f"{line[0]} {plain_text}")
    return cleaned_lines


# --- ツイート整形関連 ---
def get_text_weight(text: str) -> int:
    ascii_len = len(text.encode('ascii', 'ignore'))
    return ascii_len + (len(text) - ascii_len) * 2

def truncate_text(text: str, limit: int) -> str:
    ellipsis_w = get_text_weight(ELLIPSIS)
    current_w, truncated = 0, ""
    for char in text:
        char_w = 1 if ord(char) <= 127 else 2
        if current_w + char_w > (limit - ellipsis_w): break
        truncated += char
        current_w += char_w
    return truncated + ELLIPSIS

def format_tweets(lines: List[str]) -> List[str]:
    if not lines: return []
    tweets, current_buffer = [], ""
    current_w = 0

    for line in lines:
        line_w = get_text_weight(line)
        
        if current_buffer:
            if current_w + line_w + 1 <= CHARACTER_LIMIT:
                current_buffer += f"\n{line}"
                current_w += line_w + 1
                continue
            else:
                tweets.append(current_buffer)
                current_buffer = ""
                current_w = 0
        
        if line_w > CHARACTER_LIMIT:
            tweets.append(truncate_text(line, CHARACTER_LIMIT))
        else:
            current_buffer = line
            current_w = line_w

    if current_buffer:
        if current_w <= (CHARACTER_LIMIT - TWITTER_URL_WEIGHT - 1):
            tweets.append(f"{current_buffer}\n{CHANGELOG_URL}")
        else:
            tweets.append(current_buffer)
            tweets.append(CHANGELOG_URL)
    else:
        tweets.append(CHANGELOG_URL)
        
    return tweets


# --- X 投稿関連 ---
def post_to_x(tweets: List[str]):
    creds = {
        "consumer_key": os.getenv("X_API_KEY"),
        "consumer_secret": os.getenv("X_API_SECRET"),
        "access_token": os.getenv("X_ACCESS_TOKEN"),
        "access_token_secret": os.getenv("X_ACCESS_TOKEN_SECRET")
    }
    if not all(creds.values()):
        print("Error: X API credentials missing.")
        return

    client = tweepy.Client(**creds)
    last_id = None

    for i, content in enumerate(tweets):
        success = False
        for attempt in range(3):
            try:
                kwargs = {"text": content}
                if last_id: kwargs["in_reply_to_tweet_id"] = last_id
                
                response = client.create_tweet(**kwargs)
                last_id = response.data['id']
                print(f"Post Success: Tweet {i+1}")
                success = True
                break
            except Exception as e:
                print(f"Post Attempt {attempt+1} failed: {e}")
                time.sleep(10)
        if not success: break


# --- メイン処理 ---
if __name__ == "__main__":
    base_sha = os.getenv("LAST_SHA")
    head_sha = os.getenv("LATEST_SHA")
    
    print(f"Checking diff: {base_sha} -> {head_sha}")
    
    diff_lines = fetch_changelog_diff(base_sha, head_sha)
    if not diff_lines:
        print("No meaningful changes to tweet.")
    else:
        tweet_list = format_tweets(diff_lines)
        print(f"Generated {len(tweet_list)} tweets. Posting...")
        post_to_x(tweet_list)
