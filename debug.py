"""Run this once to print the raw API response and headers."""
import json
import requests

url = "https://graphql.haraj.com.sa/"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Origin": "https://haraj.com.sa",
    "Referer": "https://haraj.com.sa/",
    "Accept": "application/json, text/plain, */*",
}
payload = {
    "operationName": "searchPosts",
    "variables": {"query": "كورفيت", "page": 1, "size": 5, "sort": "date"},
    "query": "query searchPosts($query: String!, $page: Int, $size: Int, $sort: String) { postSearch(query: $query, page: $page, size: $size, sort: $sort) { results { id title price city } total } }"
}

r = requests.post(url, json=payload, headers=headers, timeout=20)
print("Status:", r.status_code)
print("Response headers:")
for k, v in r.headers.items():
    print(f"  {k}: {v}")
print("Body:", r.text[:2000] or "(empty)")
