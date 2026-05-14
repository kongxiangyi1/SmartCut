import psutil
import subprocess
import time
import os
import sys

BACKEND_DIR = r'e:\ClipProject\autoclip-main1\autoclip-main'
LOG_FILE = os.path.join(BACKEND_DIR, 'logs', 'backend.log')

def print_log_section(title):
    print("\n" + "=" * 70)
    print(f"📜 {title}")
    print("=" * 70)

print_log_section("启动后端服务")

# 检查端口8000
port_running = False
for conn in psutil.net_connections():
    if conn.laddr.port == 8000 and conn.status == 'LISTEN':
        port_running = True
        break

if port_running:
    print("✅ 后端服务已在运行")
else:
    print("❌ 后端服务未运行，正在启动...")

    cmd = ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

    process = subprocess.Popen(
        cmd,
        cwd=BACKEND_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    print(f"启动命令: {' '.join(cmd)}")
    print("\n等待服务启动...")
    time.sleep(20)

    # 收集启动日志
    startup_logs = []
    if process.stdout:
        for _ in range(30):
            line = process.stdout.readline()
            if line:
                startup_logs.append(line.strip())
                print(f"  {line.strip()}")
            else:
                break

    # 验证服务是否启动
    port_running = False
    for conn in psutil.net_connections():
        if conn.laddr.port == 8000 and conn.status == 'LISTEN':
            port_running = True
            break

    if not port_running:
        print("❌ 后端服务启动失败!")
        exit(1)

print("\n" + "=" * 70)
print("✅ 后端服务已启动")
print("=" * 70)

# 等待几秒让服务稳定
time.sleep(3)

print_log_section("检查项目状态")

import requests
project_id = "52cda853-3698-4fc3-820e-b62464d7f174"

try:
    resp = requests.get(f"http://localhost:8000/api/v1/projects/{project_id}", timeout=10)
    print(f"API响应状态: {resp.status_code}")
    if resp.status_code == 200:
        project = resp.json()
        print(f"\n项目名称: {project.get('name')}")
        print(f"项目状态: {project.get('status')}")
        print(f"项目进度: {project.get('progress', 0)}%")
        print(f"视频路径: {project.get('video_path')}")
except Exception as e:
    print(f"获取项目状态失败: {e}")

print_log_section("持续跟踪处理进度 (60秒)")

import signal

def signal_handler(sig, frame):
    print("\n检测到中断信号，停止跟踪")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# 跟踪60秒
for i in range(12):  # 12 * 5 = 60秒
    try:
        resp = requests.get(f"http://localhost:8000/api/v1/projects/{project_id}", timeout=5)
        if resp.status_code == 200:
            project = resp.json()
            status = project.get('status')
            progress = project.get('progress', 0)

            resp_tasks = requests.get(f"http://localhost:8000/api/v1/tasks?project_id={project_id}", timeout=5)
            task_info = ""
            if resp_tasks.status_code == 200:
                tasks = resp_tasks.json()
                if tasks:
                    task = tasks[0]
                    task_info = f"任务状态: {task.get('status'):10s} | 进度: {task.get('progress', 0):3.0f}% | 步骤: {task.get('current_step', 'N/A')}"

            print(f"[{i*5:2d}秒] 项目状态: {status:10s} | 进度: {progress:3.0f}% | {task_info}")

            if status in ['completed', 'failed']:
                print("\n🎉 处理流程已结束!")
                break
    except Exception as e:
        print(f"[{i*5:2d}秒] 错误: {e}")

    time.sleep(5)

print_log_section("流程分析报告")

# 最终状态检查
try:
    resp = requests.get(f"http://localhost:8000/api/v1/projects/{project_id}", timeout=10)
    if resp.status_code == 200:
        project = resp.json()
        print(f"\n📌 项目: {project.get('name')}")
        print(f"📌 最终状态: {project.get('status')}")
        print(f"📌 最终进度: {project.get('progress', 0)}%")

        resp_tasks = requests.get(f"http://localhost:8000/api/v1/tasks?project_id={project_id}", timeout=10)
        if resp_tasks.status_code == 200:
            tasks = resp_tasks.json()
            for task in tasks:
                print(f"\n📌 任务: {task.get('name')}")
                print(f"   状态: {task.get('status')}")
                print(f"   进度: {task.get('progress', 0)}%")
                print(f"   步骤: {task.get('current_step', 'N/A')}")
                if task.get('error_message'):
                    print(f"   ❌ 错误: {task.get('error_message')}")

        resp_clips = requests.get(f"http://localhost:8000/api/v1/clips?project_id={project_id}", timeout=10)
        if resp_clips.status_code == 200:
            clips = resp_clips.json()
            print(f"\n📌 生成切片数: {len(clips) if isinstance(clips, list) else len(clips.get('items', []))}")

        resp_collections = requests.get(f"http://localhost:8000/api/v1/collections?project_id={project_id}", timeout=10)
        if resp_collections.status_code == 200:
            collections = resp_collections.json()
            print(f"📌 生成合集数: {len(collections) if isinstance(collections, list) else len(collections.get('items', []))}")
except Exception as e:
    print(f"获取最终状态失败: {e}")

print("\n" + "=" * 70)