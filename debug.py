"""Diagnostic script — tests multiple request variations against the Haraj API."""
import gzip
import json
import requests

URL = "https://graphql.haraj.com.sa/"
PAYLOAD = {
    "operationName": "searchPosts",
    "variables": {"query": "كورفيت", "page": 1, "size": 5, "sort": "date"},
    "query": "query searchPosts($query: String!, $page: Int, $size: Int, $sort: String) { postSearch(query: $query, page: $page, size: $size, sort: $sort) { results { id title price city } total } }"
}

BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ar-SA,ar;q=0.9,en-US;q=0.8,en;q=0.7",
    "Content-Type": "application/json",
    "Origin": "https://haraj.com.sa",
    "Referer": "https://haraj.com.sa/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "Sec-CH-UA": '"Google Chrome";v="125", "Chromium";v="125", "Not/A)Brand";v="8"',
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"Windows"',
}

def try_request(label, headers):
    print(f"\n{'='*60}")
    print(f"TEST: {label}")
    print('='*60)
    try:
        r = requests.post(URL, json=PAYLOAD, headers=headers, timeout=20, stream=True)
        print(f"Status: {r.status_code}")

        # Read raw bytes before any decoding
        raw = r.raw.read(decode_content=False)
        print(f"Raw bytes length: {len(raw)}")
        if raw:
            print(f"Raw bytes (first 100): {raw[:100]}")
            # Try manual gzip decompression
            try:
                decompressed = gzip.decompress(raw)
                print(f"Gzip decompressed: {decompressed[:500]}")
            except Exception as e:
                print(f"Not gzip or decompress failed: {e}")
                print(f"Raw as text: {raw.decode('utf-8', errors='replace')[:500]}")
        else:
            print("Body: (empty — server sent nothing)")
    except Exception as e:
        print(f"Request failed: {e}")

# Test 1: No Accept-Encoding (force plain text response)
try_request(
    "No Accept-Encoding (plain text)",
    {**BASE_HEADERS}
)

# Test 2: With Accept-Encoding gzip
try_request(
    "With Accept-Encoding: gzip",
    {**BASE_HEADERS, "Accept-Encoding": "gzip, deflate, br"}
)

# Test 3: Minimal headers — just User-Agent and Content-Type
try_request(
    "Minimal headers",
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
    }
)
