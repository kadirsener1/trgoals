# proxy.py — pip install flask requests
from flask import Flask, request, Response
import requests

app = Flask(__name__)

REFERER    = "https://patronizle35.cfd/"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

@app.route("/stream")
def stream():
    target_url = request.args.get("url")
    if not target_url:
        return "?url= parametresi eksik", 400

    resp = requests.get(
        target_url,
        headers={
            "Referer":    REFERER,
            "User-Agent": USER_AGENT,
            "Origin":     REFERER.rstrip("/"),
        },
        stream=True,
        timeout=15,
    )

    headers = {
        "Content-Type":  resp.headers.get("Content-Type", "application/vnd.apple.mpegurl"),
        "Access-Control-Allow-Origin": "*",
    }
    return Response(resp.iter_content(chunk_size=4096), headers=headers)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8888, debug=False)
