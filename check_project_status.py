import requests
import sqlite3

BASE_URL = "http://localhost:8000"

print("=" * 70)
print("📊 项目状态检查")
print("=" * 70)

conn = sqlite3.connect(r'e:\ClipProject\autoclip-main1\autoclip-main\data\autoclip.db')
cursor = conn.cursor()

cursor.execute("SELECT id, name, status FROM projects ORDER BY updated_at DESC LIMIT 5")
projects = cursor.fetchall()
print(f"\n数据库中的项目:")
for p in projects:
    print(f"  ID: {p[0]}")
    print(f"  名称: {p[1]}")
    print(f"  状态: {p[2]}")
    print()

conn.close()

print("\n" + "-" * 70)
print("通过API检查项目状态...")
print("-" * 70)

for p in projects:
    project_id = p[0]
    try:
        resp = requests.get(f"{BASE_URL}/api/v1/projects/{project_id}", timeout=5)
        if resp.status_code == 200:
            project = resp.json()
            print(f"\n项目: {project.get('name')}")
            print(f"  API状态: {project.get('status')}")
            print(f"  进度: {project.get('progress', 0)}%")

            resp_tasks = requests.get(f"{BASE_URL}/api/v1/tasks?project_id={project_id}", timeout=5)
            if resp_tasks.status_code == 200:
                tasks = resp_tasks.json()
                for task in tasks:
                    print(f"  任务: {task.get('name')}")
                    print(f"  任务状态: {task.get('status')}")
                    print(f"  任务进度: {task.get('progress', 0)}%")
                    print(f"  当前步骤: {task.get('current_step', 'N/A')}")
        else:
            print(f"\n项目 {project_id}: API返回 {resp.status_code}")
    except Exception as e:
        print(f"\n项目 {project_id}: 连接失败 - {e}")

print("\n" + "=" * 70)