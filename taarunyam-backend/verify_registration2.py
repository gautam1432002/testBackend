import requests
import json

url = "http://localhost:8000/api/participants/register/"
headers = {"Content-Type": "application/json"}

# Test 1: Register for AI Challenge
payload1 = {
    "name": "Jane Tester",
    "email": "jane@example.com",
    "mobile": "9988776655",
    "college": "Test College",
    "course": "B.Tech IT",
    "year": "2nd Year",
    "events": ["ai-challenge"]
}

# Test 2: Register for Web Master
payload2 = {
    "name": "Jane Tester",
    "email": "jane@example.com",
    "mobile": "9988776655",
    "college": "Test College",
    "course": "B.Tech IT",
    "year": "2nd Year",
    "events": ["web-master"]
}

print("Running Test 1 (ai-challenge)...")
r1 = requests.post(url, json=payload1, headers=headers)
print(f"Status: {r1.status_code}")
print(r1.text)

print("\nRunning Test 2 (web-master)...")
r2 = requests.post(url, json=payload2, headers=headers)
print(f"Status: {r2.status_code}")
print(r2.text)
