import requests

BASE_URL = "http://localhost:8000"
project_id = "52cda853-3698-4fc3-820e-b62464d7f174"

print("=" * 70)
print("🔍 调试检查")
print("=" * 70)

print("\n1️⃣ 获取项目信息...")
resp = requests.get(f"{BASE_URL}/api/v1/projects/{project_id}", timeout=10)
if resp.status_code == 200:
    project = resp.json()
    print(f"✅ 项目: {project.get('name')}")
    print(f"   状态: {project.get('status')}")
    print(f"   进度: {project.get('progress')}")
    print(f"\n完整项目信息:\n{project}")

print("\n2️⃣ 获取项目的任务列表...")
resp_tasks = requests.get(f"{BASE_URL}/api/v1/tasks?project_id={project_id}", timeout=10)
print(f"响应状态: {resp_tasks.status_code}")
if resp_tasks.status_code == 200:
    tasks = resp_tasks.json()
    print(f"✅ 任务数量: {len(tasks)}")
    for i, task in enumerate(tasks):
        print(f"\n任务{i+1}:")
        print(f"  ID: {task.get('id')}")
        print(f"  CeleryID: {task.get('celery_task_id')}")
        print(f"  名称: {task.get('name')}")
        print(f"  状态: {task.get('status')}")
        print(f"  进度: {task.get('progress')}")
        print(f"  步骤: {task.get('current_step')}")
        if task.get('error_message'):
            print(f"  ❌ 错误: {task.get('error_message')}")

print("\n" + "=" * 70)