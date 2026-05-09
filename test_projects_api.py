import requests
import json

response = requests.get("http://localhost:8000/api/v1/projects/")
print(f"状态码: {response.status_code}")

data = response.json()
print(f"项目数量: {len(data['items'])}")
if data['items']:
    print(f"第一个项目ID: {data['items'][0]['id']}")
    print(f"第一个项目状态: {data['items'][0]['status']}")