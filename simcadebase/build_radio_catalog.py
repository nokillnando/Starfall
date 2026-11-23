#!/usr/bin/env python3
"""
Extract rRadio's builtin_registry.lua station catalog into per-country JSON files
suitable for lazy-loading in Starfall via raw.githubusercontent.com.

Output:
  simcadebase/radio_catalog/index.json
      [[countryKey, displayName, stationCount], ...]
  simcadebase/radio_catalog/countries/<countryKey>.json
      [[stationName, streamUrl], ...]
"""

import base64
import hashlib
import json
import lzma
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_FILE = os.path.join(
    ROOT, "radioaddon", "lua", "rradio", "server", "stations", "builtin_registry.lua"
)
OUT_DIR = os.path.join(ROOT, "simcadebase", "radio_catalog")
COUNTRIES_DIR = os.path.join(OUT_DIR, "countries")

SPECIAL_NAMES = {
    "aland_islands": "Aland Islands",
    "bosnia_and_herzegovina": "Bosnia and Herzegovina",
    "british_virgin_islands": "British Virgin Islands",
    "cape_verde": "Cape Verde",
    "cayman_islands": "Cayman Islands",
    "central_african_republic": "Central African Republic",
    "congo_democratic_republic": "DR Congo",
    "costa_rica": "Costa Rica",
    "cote_divoire": "Cote d'Ivoire",
    "czech_republic": "Czech Republic",
    "dominican_republic": "Dominican Republic",
    "el_salvador": "El Salvador",
    "equatorial_guinea": "Equatorial Guinea",
    "falkland_islands": "Falkland Islands",
    "faroe_islands": "Faroe Islands",
    "french_guiana": "French Guiana",
    "french_polynesia": "French Polynesia",
    "hong_kong": "Hong Kong",
    "isle_of_man": "Isle of Man",
    "new_caledonia": "New Caledonia",
    "new_zealand": "New Zealand",
    "north_korea": "North Korea",
    "north_macedonia": "North Macedonia",
    "papua_new_guinea": "Papua New Guinea",
    "puerto_rico": "Puerto Rico",
    "saint_kitts_and_nevis": "Saint Kitts and Nevis",
    "saint_lucia": "Saint Lucia",
    "saint_vincent_and_the_grenadines": "Saint Vincent and the Grenadines",
    "san_marino": "San Marino",
    "sao_tome_and_principe": "Sao Tome and Principe",
    "saudi_arabia": "Saudi Arabia",
    "sierra_leone": "Sierra Leone",
    "solomon_islands": "Solomon Islands",
    "south_africa": "South Africa",
    "south_korea": "South Korea",
    "south_sudan": "South Sudan",
    "sri_lanka": "Sri Lanka",
    "trinidad_and_tobago": "Trinidad and Tobago",
    "turks_and_caicos_islands": "Turks and Caicos Islands",
    "united_arab_emirates": "United Arab Emirates",
    "united_kingdom": "United Kingdom",
    "united_states": "United States",
    "us_virgin_islands": "US Virgin Islands",
    "vatican_city": "Vatican City",
}


def format_country_name(key: str) -> str:
    if key in SPECIAL_NAMES:
        return SPECIAL_NAMES[key]
    words = key.split("_")
    small = {"and", "of", "the", "da", "de", "do"}
    out = []
    for i, w in enumerate(words):
        if i > 0 and w in small:
            out.append(w)
        else:
            out.append(w.capitalize())
    return " ".join(out)


def main() -> int:
    if not os.path.isfile(SOURCE_FILE):
        print(f"ERROR: Source file not found: {SOURCE_FILE}", file=sys.stderr)
        return 1

    with open(SOURCE_FILE, "r", encoding="utf-8") as f:
        text = f.read()

    m_data = re.search(r"data\s*=\s*\[\[(.*?)\]\]", text, re.S)
    if not m_data:
        print("ERROR: Could not find base64 payload in builtin_registry.lua", file=sys.stderr)
        return 1

    raw = base64.b64decode(m_data.group(1))
    uncompressed_size = struct.unpack("<Q", raw[5:13])[0]
    props = lzma._decode_filter_properties(lzma.FILTER_LZMA1, raw[:5])
    decomp = lzma.LZMADecompressor(lzma.FORMAT_RAW, filters=[props])
    decoded_bytes = decomp.decompress(raw[13:], max_length=uncompressed_size)

    m_sha = re.search(r'sha256\s*=\s*"([0-9a-f]+)"', text)
    if m_sha:
        actual = hashlib.sha256(decoded_bytes).hexdigest()
        if actual != m_sha.group(1):
            print(f"ERROR: SHA256 mismatch ({actual} != {m_sha.group(1)})", file=sys.stderr)
            return 1

    payload = json.loads(decoded_bytes.decode("utf-8"))
    countries = payload.get("countries", {})

    os.makedirs(COUNTRIES_DIR, exist_ok=True)

    index_entries = []
    total_stations = 0
    largest = ("", 0, 0)

    for key, stations_map in countries.items():
        if not isinstance(stations_map, dict) or not stations_map:
            continue

        rows = []
        seen_urls = set()
        for _sid, entry in stations_map.items():
            if not isinstance(entry, list) or len(entry) < 2:
                continue
            name = str(entry[0] or "").strip()
            url = str(entry[1] or "").strip()
            if not name or not url or url in seen_urls:
                continue
            seen_urls.add(url)
            rows.append([name, url])

        if not rows:
            continue

        rows.sort(key=lambda r: (r[0].lower(), r[0]))
        safe_key = re.sub(r"[^a-z0-9_-]", "_", key.lower())
        out_path = os.path.join(COUNTRIES_DIR, f"{safe_key}.json")
        serialized = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
        with open(out_path, "w", encoding="utf-8", newline="\n") as out_f:
            out_f.write(serialized)

        size_bytes = len(serialized.encode("utf-8"))
        if size_bytes > largest[1]:
            largest = (safe_key, size_bytes, len(rows))

        display_name = format_country_name(safe_key)
        index_entries.append([safe_key, display_name, len(rows)])
        total_stations += len(rows)

    index_entries.sort(key=lambda e: e[1].lower())
    index_path = os.path.join(OUT_DIR, "index.json")
    index_json = json.dumps(index_entries, ensure_ascii=False, separators=(",", ":"))
    with open(index_path, "w", encoding="utf-8", newline="\n") as idx_f:
        idx_f.write(index_json)

    print(f"Extracted {len(index_entries)} countries, {total_stations} unique stations.")
    print(f"Index size: {len(index_json.encode('utf-8'))} bytes -> {index_path}")
    print(f"Largest country: {largest[0]} ({largest[2]} stations, {largest[1]} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
