"""Run this once to print the raw API response and headers."""
import json
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ar-SA,ar;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Content-Type": "application/json",
    "Origin": "https://haraj.com.sa",
    "Referer": "https://haraj.com.sa/",
    "DNT": "1",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "Sec-CH-UA": '"Google Chrome";v="125", "Chromium";v="125", "Not/A)Brand";v="8"',
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"Windows"',
    "Sec-CH-UA-Arch": '"x86"',
    "Sec-CH-UA-Bitness": '"64"',
    "Sec-CH-UA-Full-Version-List": '"Google Chrome";v="125.0.6422.112", "Chromium";v="125.0.6422.112", "Not/A)Brand";v="8.0.0.0"',
}

payload = {
    "operationName": "searchPosts",
    "variables": {"query": "كورفيت", "page": 1, "size": 5, "sort": "date"},
    "query": "query searchPosts($query: String!, $page: Int, $size: Int, $sort: String) { postSearch(query: $query, page: $page, size: $size, sort: $sort) { results { id title price city } total } }"
}

session = requests.Session()
print("Warming up session via haraj.com.sa...")
session.get("https://haraj.com.sa/", headers={k: v for k, v in HEADERS.items() if k != "Content-Type"}, timeout=20)
print(f"Cookies after warmup: {dict(session.cookies)}\n")

r = session.post("https://graphql.haraj.com.sa/", json=payload, headers=HEADERS, timeout=20)
print("Status:", r.status_code)
print("Response headers:")
for k, v in r.headers.items():
    print(f"  {k}: {v}")
print("Body:", r.text[:2000] or "(empty)")
