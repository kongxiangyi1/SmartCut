import requests
import time

BASE_URL = "http://localhost:8000"
project_id = "52cda853-3698-4fc3-820e-b62464d7f174"

print("=" * 70)
print("🚀 检查并触发项目处理")
print("=" * 70)

# 1. 检查服务
print("\n1️⃣ 检查后端服务...")
try:
    resp = requests.get(f"{BASE_URL}/api/v1/health", timeout=5)
    print("✅ 后端服务正常")
except Exception as e:
    print(f"❌ 后端服务异常: {e}")
    exit(1)

# 2. 检查项目
print("\n2️⃣ 检查项目状态...")
resp = requests.get(f"{BASE_URL}/api/v1/projects/{project_id}", timeout=10)
if resp.status_code == 200:
    project = resp.json()
    print(f"✅ 项目: {project.get('name')}")
    print(f"   状态: {project.get('status')}")

    # 3. 如果是pending，触发处理
    if project.get('status') == 'pending':
        print("\n3️⃣ 触发处理...")
        resp_process = requests.post(f"{BASE_URL}/api/v1/projects/{project_id}/process", timeout=30)
        print(f"响应状态: {resp_process.status_code}")
        print(f"响应内容: {resp_process.text}")
else:
    print(f"❌ 获取项目失败: {resp.status_code}")

print("\n" + "=" * 70)