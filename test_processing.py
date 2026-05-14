import requests
import json
import time

BASE_URL = "http://localhost:8000"

project_id = "494c9b44-b094-4df4-951a-913b6e70d8a0"

print("=" * 60)
print("🚀 启动项目处理")
print("=" * 60)

# 1. 先获取项目详情
print("\n1. 获取项目详情...")
try:
    resp = requests.get(f"{BASE_URL}/api/v1/projects/{project_id}", timeout=10)
    print(f"状态码: {resp.status_code}")
    if resp.status_code == 200:
        project = resp.json()
        print(f"项目名称: {project.get('name')}")
        print(f"项目状态: {project.get('status')}")
        print(f"项目类型: {project.get('project_type')}")
    else:
        print(f"响应: {resp.text}")
except Exception as e:
    print(f"错误: {e}")

# 2. 启动处理
print("\n2. 启动项目处理...")
try:
    resp = requests.post(f"{BASE_URL}/api/v1/projects/{project_id}/process", timeout=30)
    print(f"状态码: {resp.status_code}")
    print(f"响应: {resp.text}")
except Exception as e:
    print(f"错误: {e}")

# 3. 等待几秒
print("\n3. 等待5秒后检查状态...")
time.sleep(5)

# 4. 再次获取项目详情
print("\n4. 再次获取项目详情...")
try:
    resp = requests.get(f"{BASE_URL}/api/v1/projects/{project_id}", timeout=10)
    print(f"状态码: {resp.status_code}")
    if resp.status_code == 200:
        project = resp.json()
        print(f"项目名称: {project.get('name')}")
        print(f"项目状态: {project.get('status')}")
        print(f"详细响应: {json.dumps(project, indent=2, ensure_ascii=False)}")
    else:
        print(f"响应: {resp.text}")
except Exception as e:
    print(f"错误: {e}")

# 5. 检查任务列表
print("\n5. 获取任务列表...")
try:
    resp = requests.get(f"{BASE_URL}/api/v1/tasks/?project_id={project_id}", timeout=10)
    print(f"状态码: {resp.status_code}")
    if resp.status_code == 200:
        tasks = resp.json()
        print(f"任务数: {len(tasks.get('items', []))}")
        for task in tasks.get('items', []):
            print(f"  - 任务: {task.get('name')}, 状态: {task.get('status')}, 进度: {task.get('progress')}%")
    else:
        print(f"响应: {resp.text}")
except Exception as e:
    print(f"错误: {e}")

print("\n" + "=" * 60)