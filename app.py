import json
import urllib.request
import urllib.error
from flask import Flask, render_template, request, jsonify

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

For each car found, provide:

- Year, Model, Trim
- Mileage
- Price
- Dealer name and location (city, state)
- VIN (if visible in listing)
- Link to listing (if available)
- Confirmed features from listing (especially: ventilated seats, adaptive cruise control, panoramic roof)
- Any red flags (accidents, branded title, high miles, suspicious history, multiple owners)
- Porsche CPO status if applicable
- Estimated distance from Dallas-Fort Worth, TX
- A brief verdict: Good / Caution / Avoid

If you find a VIN, also search visor.vin for that VIN to check vehicle history, title status, \
and any reported issues. Include any visor.vin findings in your results.

CARFAX - ALWAYS SURFACE PROMINENTLY:
- For every car with a visible VIN, include a direct CARFAX link: https://www.carfax.com/VehicleHistory/p/Report.cfx?vin=XXXXX
- Many dealer sites have free CARFAX reports buried in the listing. If you find a CARFAX report link \
on a dealer page, include it prominently.
- Summarize key CARFAX findings: number of owners, accident history, service records, title status.
- Put the CARFAX link right after the VIN so it's easy to click.

Format your response as a clean structured list with clear separators between each car. \
Be thorough - search multiple sites. If a listing doesn't confirm all three must-have features, \
note which are unconfirmed. Always note if the car is Porsche CPO.

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
Note distance and shipping considerations when relevant."""


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

    max_uses = body.get("max_uses", 10)
    if not isinstance(max_uses, int) or max_uses < 1:
        max_uses = 10
    if max_uses > 20:
        max_uses = 20

    payload = json.dumps({
        "model": "claude-sonnet-4-6",
        "max_tokens": 8000,
        "system": SYSTEM_PROMPT,
        "tools": [
            {"type": "web_search_20260209", "name": "web_search", "max_uses": max_uses}
        ],
        "messages": [
            {"role": "user", "content": query}
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
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
            return app.response_class(data, status=resp.status, mimetype="application/json")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        return app.response_class(error_body, status=e.code, mimetype="application/json")
    except Exception as e:
        return jsonify({"error": f"Proxy error: {str(e)}"}), 502


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
