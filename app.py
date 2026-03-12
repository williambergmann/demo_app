import json
import urllib.request
import urllib.error
from flask import Flask, render_template, request, jsonify, Response
import re

app = Flask(__name__)

SEARCH_PRESETS = [
    {
        "label": "Base Cayenne \u2013 Texas",
        "query": "Used 2019-2024 Porsche Cayenne base, $25K-$35K, in or near Texas. Prioritize one-owner, low-mileage.",
    },
    {
        "label": "Base Cayenne \u2013 Nationwide",
        "query": "Used 2019-2024 Porsche Cayenne base, $25K-$35K, nationwide US. Prioritize one-owner, low-mileage, clean CARFAX.",
    },
    {
        "label": "E-Hybrid \u2013 CARB States",
        "query": "Used 2020-2024 Porsche Cayenne E-Hybrid, $28K-$38K, in CA/OR/WA/CARB states. Prefer 7.2 kW charger and Sport Chrono. Flag CARB-state original sale (10yr/150K battery warranty) and any HV battery issues.",
    },
    {
        "label": "E-Hybrid \u2013 Nationwide",
        "query": "Used 2020-2024 Porsche Cayenne E-Hybrid, under $38K, nationwide. Flag CARB-state original sale (better battery warranty) and any HV battery issues.",
    },
    {
        "label": "Cayenne S \u2013 Texas",
        "query": "Used 2019-2023 Porsche Cayenne S, $30K-$42K, in Texas. Prefer Porsche CPO.",
    },
    {
        "label": "Feeling Lucky",
        "query": "Find me ONE specific 2019 Porsche Cayenne currently for sale anywhere in the US. Just pick the first real listing you find on any site. Give me the full details on that single car.",
        "max_uses": 3,
    },
]

SYSTEM_PROMPT = """You are a used car research assistant specializing in Porsche Cayenne vehicles. \
Search the web thoroughly using multiple car listing sites including cars.com, carvana.com, carmax.com, \
edmunds.com, carfax.com, autotrader.com, cargurus.com, autotempest.com, and visor.vin.

If you find a VIN, also search visor.vin for that VIN to check vehicle history, title status, \
and any reported issues.

CRITICAL FEATURE DISTINCTIONS — The three must-have features require careful verification:

1. ADAPTIVE CRUISE CONTROL (ACC) — NOT regular cruise control:
- Every car has basic cruise control. The buyer needs ADAPTIVE/RADAR-BASED cruise that maintains \
distance from the car ahead automatically.
- Acceptable terms: "Adaptive Cruise Control", "Active Cruise Control", "ACC", \
"Adaptive Cruise Control with Stop-and-Go".
- On Porsche Cayenne, ACC comes with the Premium Plus Package. If listing shows Premium Plus \
Package, ACC is confirmed.
- If a listing only says "cruise control" without "adaptive", mark ACC as UNCONFIRMED.

2. VENTILATED / COOLED SEATS — NOT just heated seats:
- The buyer needs VENTILATED or COOLED front seats (the ones that blow cold air through perforations).
- Acceptable terms: "ventilated seats", "cooled seats", "cooling seats", "heated and ventilated seats", \
"heated and cooled seats".
- "Heated seats" alone does NOT confirm ventilation. Almost every Cayenne has heated seats.
- On Porsche Cayenne, ventilated seats come with the Premium Plus Package or the 18-way Comfort Seats \
with ventilation option.
- If a listing only says "heated seats" or "leather seats" without mentioning ventilation/cooling, \
mark ventilated seats as UNCONFIRMED.

3. PANORAMIC ROOF — NOT a standard sunroof:
- The buyer needs a PANORAMIC roof (full-length glass roof that extends over rear passengers).
- Acceptable terms: "panoramic roof", "panoramic sunroof", "panoramic roof system", "pano roof".
- A standard small "sunroof" or "moonroof" does NOT count — those are the smaller tilt-and-slide type.
- On Porsche Cayenne, the panoramic roof is a distinct option from the standard sunroof. \
Look for "panoramic" specifically.
- If a listing only says "sunroof" or "moonroof" without "panoramic", mark panoramic roof as UNCONFIRMED.

For all three features: If the listing mentions Premium Plus Package, you can assume all three are included \
(ACC, ventilated seats, and panoramic roof all come in that package on the Cayenne).

IMPORTANT: The buyer is located in the Dallas-Fort Worth area of Texas. \
Note distance and shipping considerations when relevant.

OUTPUT FORMAT — You MUST respond with ONLY a JSON array. No markdown, no explanation, no extra text. \
Each element represents one vehicle listing:

[
  {
    "year": 2019,
    "model": "Cayenne",
    "trim": "Base",
    "price": "$29,500",
    "mileage": "45,000 mi",
    "dealer": "Platinum Auto Haus",
    "location": "Dallas, TX",
    "vin": "WP1AA2AY3KDA12345",
    "listing_url": "https://...",
    "image_url": "https://...(main photo URL from listing)...",
    "carfax_url": "https://...(free dealer-provided CARFAX link, or null)...",
    "features_confirmed": ["Ventilated Seats", "Adaptive Cruise Control", "Panoramic Roof"],
    "features_unconfirmed": ["Panoramic Roof"],
    "red_flags": ["2 owners"],
    "verdict": "Good",
    "cpo": false,
    "distance_from_dfw": "~15 miles",
    "owners": "2",
    "notes": "Clean CARFAX, well-maintained"
  }
]

Rules for JSON output:
- image_url: IMPORTANT — always try to find the main photo URL for the listing. Look for og:image meta tags, \
CDN image URLs (e.g. from cargurus, cars.com, carvana media servers), or any direct .jpg/.png image URL shown \
in the search results for that vehicle. If you find multiple images, pick the best exterior shot. \
Only use null if you truly cannot find any image URL.
- verdict must be one of: "Good", "Caution", "Avoid"
- features_confirmed: only features explicitly confirmed in the listing
- features_unconfirmed: the three must-have features NOT confirmed (from: Ventilated Seats, \
Adaptive Cruise Control, Panoramic Roof)
- If VIN is available, ALWAYS include it
- carfax_url: If the dealer or listing site provides a FREE CARFAX report link, include it. \
Do NOT generate a carfax.com paid report URL. Only include URLs that lead to free, \
dealer-provided CARFAX reports (often on the listing page itself). Use null if no free report is available.
- Output ONLY the JSON array. No other text before or after it."""


@app.route("/")
def index():
    return render_template("cayenne.html")


@app.route("/search", methods=["POST"])
def search():
    api_key = request.headers.get("X-Api-Key", "")
    if not api_key:
        return jsonify({"error": "API key is required"}), 401

    body = request.get_json(silent=True) or {}
    query = body.get("query", "").strip()
    if not query:
        return jsonify({"error": "Query is required"}), 400

    max_uses = body.get("max_uses", 5)
    if not isinstance(max_uses, int) or max_uses < 1:
        max_uses = 5
    if max_uses > 20:
        max_uses = 20

    payload = json.dumps({
        "model": "claude-sonnet-4-6",
        "max_tokens": 16000,
        "stream": True,
        "system": SYSTEM_PROMPT,
        "tools": [
            {"type": "web_search_20250305", "name": "web_search", "max_uses": max_uses}
        ],
        "messages": [
            {"role": "user", "content": query + "\n\nRemember: respond with ONLY a raw JSON array. No markdown, no commentary, no apologies. Start your response with [ and end with ]."}
        ],
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    try:
        resp = urllib.request.urlopen(req, timeout=300)
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        return app.response_class(error_body, status=e.code, mimetype="application/json")
    except Exception as e:
        return jsonify({"error": f"Proxy error: {str(e)}"}), 502

    def generate():
        try:
            for line in resp:
                yield line
        finally:
            resp.close()

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
