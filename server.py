from flask import Flask, request, jsonify
from accessiscan.api.crawler import crawl_sync

app = Flask(__name__)


@app.route("/scan", methods=["POST"])
def scan():

    data = request.json
    url = data["url"]

    try:

        site_data = crawl_sync(url)

        return jsonify({
            "status": "success",
            "text_length": len(site_data["markdown"]),
            "screenshot_captured": site_data["screenshot"] is not None
        })

    except Exception as e:

        return jsonify({
            "status": "error",
            "message": str(e)
        })


if __name__ == "__main__":
    app.run(debug=True)