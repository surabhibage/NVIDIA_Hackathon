from flask import Flask, request, jsonify
from crawler import crawl_sync
# from persona_engine import simulate_persona
# from personas import PERSONA_REGISTRY

app = Flask(__name__)


@app.route("/scan", methods=["POST"])
def scan():

    url = request.json["url"]

    # Crawl website
    site_data = crawl_sync(url)

    # persona_results = []

    # Run persona agents
    # for persona in PERSONA_REGISTRY:

    #     result = simulate_persona(persona, site_data)
    #     persona_results.append(result)

    # return jsonify(persona_results)


if __name__ == "__main__":
    app.run(debug=True)