import os
from requests_oauthlib import OAuth1Session

def post_to_x(message):
    payload = {"text": message}
    oauth = OAuth1Session(
        os.environ["X_API_KEY"],
        os.environ["X_API_SECRET"],
        os.environ["X_ACCESS_TOKEN"],
        os.environ["X_ACCESS_TOKEN_SECRET"],
    )
    response = oauth.post("https://api.twitter.com/2/tweets", json=payload)
    if response.status_code == 201:
        print("Successfully posted to X")
    else:
        print(f"Failed: {response.status_code}, {response.text}")

if __name__ == "__main__":
    msg = "CANDY HOUSEのchangelogが更新されました！\nhttps://github.com/CANDY-HOUSE/.github/commits/main/changelog.html"
    post_to_x(msg)
