#!/usr/bin/env python3
"""Fetch 3-day forecasts from Open-Meteo and write data/forecast.json.

Runs on GitHub Actions, where the live API is reachable. The Cowork sandbox
cannot reach api.open-meteo.com, but it CAN git-clone this repo, so the daily
Cowork task reads this file instead of fetching weather directly. Stdlib only.
"""
import json, datetime, urllib.request, urllib.error

LOCATIONS = [
    {"id": "woodinville", "name": "Woodinville, WA", "sub": "Home outdoor / scouting / general", "lat": 47.7462, "lon": -122.1119, "home": True},
    {"id": "cle_elum",    "name": "Cle Elum, WA",    "sub": "Upper Yakima / canyon east",        "lat": 47.1954, "lon": -120.9395},
    {"id": "north_bend",  "name": "North Bend, WA",  "sub": "Middle Fork Snoqualmie",            "lat": 47.4935, "lon": -121.7831},
    {"id": "skykomish",   "name": "Skykomish, WA",   "sub": "Skykomish town / river corridor",   "lat": 47.7094, "lon": -121.3590},
    {"id": "avery",       "name": "Avery, ID",       "sub": "Upper St. Joe corridor",            "lat": 47.2505, "lon": -115.8124},
    {"id": "riggins",     "name": "Riggins, ID",     "sub": "Salmon River corridor",             "lat": 45.4146, "lon": -116.3162},
    {"id": "blue_ridge",  "name": "Blue Ridge, GA",  "sub": "Toccoa corridor",                   "lat": 34.8423, "lon": -84.2999},
]

WMO = {
    0: "Clear", 1: "Mostly sunny", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Freezing fog", 51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
    56: "Freezing drizzle", 57: "Freezing drizzle", 61: "Light rain", 63: "Rain", 65: "Heavy rain",
    66: "Freezing rain", 67: "Freezing rain", 71: "Light snow", 73: "Snow", 75: "Heavy snow",
    77: "Snow grains", 80: "Rain showers", 81: "Rain showers", 82: "Heavy rain showers",
    85: "Snow showers", 86: "Snow showers", 95: "Thunderstorms", 96: "Thunderstorms with hail", 99: "Thunderstorms with hail",
}

def category(code):
    if code in (95, 96, 99): return "storm"
    if code in (71, 73, 75, 77, 85, 86): return "snow"
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82): return "rain"
    if code in (2, 3, 45, 48): return "cloud"
    return "clear"

def fetch(loc):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        "?latitude=%s&longitude=%s"
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code,wind_speed_10m_max"
        "&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=auto&forecast_days=4"
    ) % (loc["lat"], loc["lon"])
    req = urllib.request.Request(url, headers={"User-Agent": "weather-forecast-bot/1.0 (github.com/jimbodini19)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def build_location(loc):
    out = {"name": loc["name"], "sub": loc["sub"], "lat": loc["lat"], "lon": loc["lon"], "home": loc.get("home", False)}
    try:
        raw = fetch(loc)
        d = raw["daily"]
        days = []
        for i in range(min(3, len(d["time"]))):
            code = int(d["weather_code"][i])
            dt = datetime.date.fromisoformat(d["time"][i])
            pop = d["precipitation_probability_max"][i]
            days.append({
                "date": d["time"][i],
                "dow": dt.strftime("%a"),
                "hi": round(d["temperature_2m_max"][i]),
                "lo": round(d["temperature_2m_min"][i]),
                "precip": 0 if pop is None else int(pop),
                "code": code,
                "condition": WMO.get(code, "Unknown"),
                "category": category(code),
                "wind_mph": round(d["wind_speed_10m_max"][i]) if d.get("wind_speed_10m_max") else None,
            })
        out["ok"] = True
        out["days"] = days
        out["utc_offset_seconds"] = raw.get("utc_offset_seconds")
    except Exception as e:
        out["ok"] = False
        out["days"] = []
        out["error"] = "%s: %s" % (type(e).__name__, e)
    return out

def main():
    now = datetime.datetime.now(datetime.timezone.utc)
    pt = now.astimezone(datetime.timezone(datetime.timedelta(hours=-7)))
    locs = {loc["id"]: build_location(loc) for loc in LOCATIONS}
    doc = {
        "generated_at_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_at_pt": pt.strftime("%Y-%m-%d %H:%M PT"),
        "source": "Open-Meteo (api.open-meteo.com), WMO weather codes",
        "locations": locs,
    }
    ok = sum(1 for v in locs.values() if v["ok"])
    print("Built forecast.json: %d/%d locations ok" % (ok, len(locs)))
    if ok == 0:
        raise SystemExit("All location fetches failed; not overwriting with empty data")
    with open("data/forecast.json", "w") as f:
        json.dump(doc, f, indent=2)

if __name__ == "__main__":
    main()
