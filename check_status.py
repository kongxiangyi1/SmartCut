
import requests

project_id = "c652da34-19b0-42b2-bda8-d1fa9fa09b7b"
url = f"http://localhost:8000/api/v1/projects/{project_id}"

try:
    response = requests.get(url, timeout=10)
    print(f"响应状态码: {response.status_code}")
    print(f"响应内容: {response.text}")
except Exception as e:
    print(f"请求失败: {e}")

# 检查任务状态
url = f"http://localhost:8000/api/v1/projects/{project_id}/tasks"
try:
    response = requests.get(url, timeout=10)
    print(f"\n任务列表响应状态码: {response.status_code}")
    print(f"任务列表: {response.text}")
except Exception as e:
    print(f"获取任务列表失败: {e}")
