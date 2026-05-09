import requests
import json

response = requests.get("http://localhost:8000/api/v1/projects/")
data = response.json()

print(f"项目数量: {len(data['items'])}")
print(f"总数据大小: {len(json.dumps(data))/1024:.1f} KB")
print(f"第一项目状态: {data['items'][0]['status'] if data['items'] else 'N/A'}")
print(f"第一项目缩略图: {data['items'][0]['thumbnail'] if data['items'] else 'N/A'}")