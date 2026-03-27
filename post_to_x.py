import os
import requests
from requests_oauthlib import OAuth1Session

def get_file_diff(base, head):
    repo = "CANDY-HOUSE/.github"
    url = f"https://api.github.com/repos/{repo}/compare/{base}...{head}"
    response = requests.get(url)
    response.raise_for_status()
    
    data = response.json()
    for file in data.get("files", []):
        if file["filename"] == "changelog.html":
            # patch（差分）を取得
            patch = file.get("patch", "")
            # 「+」で始まる行（追加行）だけを抽出して要約
            added_lines = [line[1:].strip() for line in patch.split("\n") if line.startswith("+") and not line.startswith("+++")]
            return "\n".join(added_lines)
    return "詳細はGitHubを確認してください。"

def post_to_x(content):
    # Xの140/280文字制限に配慮してトリミング
    message = f"【SESAME アップデート】\n{content}"[:250] + "..."
    
    oauth = OAuth1Session(
        os.environ["X_API_KEY"],
        os.environ["X_API_SECRET"],
        os.environ["X_ACCESS_TOKEN"],
        os.environ["X_ACCESS_TOKEN_SECRET"],
    )
    payload = {"text": message}
    oauth.post("https://api.twitter.com/2/tweets", json=payload)

if __name__ == "__main__":
    # YAMLから渡された環境変数を使用
    last_sha = os.environ.get("LAST_SHA")
    latest_sha = os.environ.get("LATEST_SHA")
    
    if last_sha and latest_sha:
        diff_text = get_file_diff(last_sha, latest_sha)
        # post_to_x(diff_text)
        print(diff_text)
