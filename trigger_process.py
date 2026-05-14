
import requests
import json

project_id = "c652da34-19b0-42b2-bda8-d1fa9fa09b7b"
url = f"http://localhost:8000/api/v1/projects/{project_id}/process"

headers = {"Content-Type": "application/json"}
data = {"callback_url": ""}

print(f"触发项目处理: {project_id}")
print(f"请求URL: {url}")

try:
    response = requests.post(url, headers=headers, data=json.dumps(data))
    print(f"响应状态码: {response.status_code}")
    print(f"响应内容: {response.text}")
except Exception as e:
    print(f"请求失败: {e}")
