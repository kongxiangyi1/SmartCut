import requests
import time
import sys

BASE_URL = "http://localhost:8000"
project_id = "52cda853-3698-4fc3-820e-b62464d7f174"

def print_status():
    print("\n" + "=" * 70)
    print("📊 当前状态")
    print("=" * 70)

# 检查服务是否运行
print_status()
print("\n1️⃣ 检查后端服务...")
try:
    resp = requests.get(f"{BASE_URL}/api/v1/health", timeout=5)
    print(f"✅ 后端服务运行正常")
except Exception as e:
    print(f"❌ 后端服务连接失败: {e}")
    sys.exit(1)

# 获取项目详情
print("\n2️⃣ 获取项目详情...")
resp = requests.get(f"{BASE_URL}/api/v1/projects/{project_id}", timeout=10)
if resp.status_code == 200:
    project = resp.json()
    print(f"✅ 项目: {project.get('name')}")
    print(f"   当前状态: {project.get('status')}")
    print(f"   当前进度: {project.get('progress', 0)}%")

    # 如果是pending状态，触发处理
    if project.get('status') == 'pending':
        print("\n3️⃣ 触发项目处理...")
        resp_process = requests.post(f"{BASE_URL}/api/v1/projects/{project_id}/process", timeout=30)
        if resp_process.status_code == 200:
            process_result = resp_process.json()
            print(f"✅ 处理流程已启动!")
            print(f"   任务ID: {process_result.get('task_id')}")
        else:
            print(f"❌ 触发处理失败: {resp_process.status_code}")
            print(f"   {resp_process.text}")
            sys.exit(1)
    else:
        print(f"\n3️⃣ 跳过: 项目已经在处理中 ({project.get('status')})")
else:
    print(f"❌ 获取项目失败: {resp.status_code}")
    sys.exit(1)

print_status()
print("\n4️⃣ 开始跟踪处理进度 (每5秒更新一次)...")
print("-" * 70)

# 持续跟踪
max_checks = 120  # 最多10分钟
task_id = None

for i in range(max_checks):
    try:
        # 获取项目状态
        resp = requests.get(f"{BASE_URL}/api/v1/projects/{project_id}", timeout=10)
        if resp.status_code == 200:
            project = resp.json()
            status = project.get('status')
            progress = project.get('progress', 0)

            # 获取任务状态
            resp_tasks = requests.get(f"{BASE_URL}/api/v1/tasks?project_id={project_id}", timeout=10)
            task_info = ""
            tasks = []
            if resp_tasks.status_code == 200:
                tasks = resp_tasks.json()
                if tasks:
                    task = tasks[0]
                    task_info = f"任务状态: {task.get('status'):10s} | 进度: {task.get('progress', 0):3.0f}% | 步骤: {task.get('current_step', 'N/A')}"

            elapsed = i * 5
            print(f"[{elapsed:3d}秒] 项目状态: {status:10s} | 进度: {progress:3.0f}% | {task_info}")

            # 检查是否完成或失败
            if status == 'completed':
                print("\n" + "=" * 70)
                print("🎉 处理完成!")
                print("=" * 70)

                # 获取切片和合集信息
                resp_clips = requests.get(f"{BASE_URL}/api/v1/clips?project_id={project_id}", timeout=10)
                clips = []
                if resp_clips.status_code == 200:
                    clips_data = resp_clips.json()
                    clips = clips_data if isinstance(clips_data, list) else clips_data.get('items', [])
                    print(f"\n📌 生成切片数: {len(clips)}")

                resp_collections = requests.get(f"{BASE_URL}/api/v1/collections?project_id={project_id}", timeout=10)
                collections = []
                if resp_collections.status_code == 200:
                    coll_data = resp_collections.json()
                    collections = coll_data if isinstance(coll_data, list) else coll_data.get('items', [])
                    print(f"📌 生成合集数: {len(collections)}")

                print("\n" + "=" * 70)
                break

            if status == 'failed':
                print("\n" + "=" * 70)
                print("❌ 处理失败!")
                print("=" * 70)

                # 检查错误信息
                for task in tasks:
                    if task.get('error_message'):
                        print(f"\n错误: {task.get('error_message')}")

                print("\n" + "=" * 70)
                break

    except Exception as e:
        elapsed = i * 5
        print(f"[{elapsed:3d}秒] 错误: {e}")

    time.sleep(5)

if i == max_checks - 1:
    print("\n" + "=" * 70)
    print("⏰ 跟踪超时 (超过10分钟)")
    print("=" * 70)