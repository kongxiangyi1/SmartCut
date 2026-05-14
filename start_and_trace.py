import psutil
import subprocess
import time
import os

BACKEND_DIR = r'e:\ClipProject\autoclip-main1\autoclip-main'
LOG_FILE = os.path.join(BACKEND_DIR, 'logs', 'backend.log')

print("=" * 70)
print("🚀 启动后端服务并跟踪日志")
print("=" * 70)

# 检查端口8000是否被占用
port_8000_running = False
for conn in psutil.net_connections():
    if conn.laddr.port == 8000 and conn.status == 'LISTEN':
        port_8000_running = True
        break

if port_8000_running:
    print("✅ 后端服务已经在运行 (端口8000)")
else:
    print("❌ 后端服务未运行，正在启动...")

    # 启动后端服务
    cmd = [
        "python", "-m", "uvicorn",
        "backend.main:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--reload"
    ]

    print(f"启动命令: {' '.join(cmd)}")

    # 创建日志目录
    os.makedirs(os.path.join(BACKEND_DIR, 'logs'), exist_ok=True)

    # 启动进程
    process = subprocess.Popen(
        cmd,
        cwd=BACKEND_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    print("\n等待服务启动...")
    started = False
    for i in range(15):
        time.sleep(2)

        # 检查端口
        for conn in psutil.net_connections():
            if conn.laddr.port == 8000 and conn.status == 'LISTEN':
                print("✅ 后端服务启动成功!")
                started = True
                break

        if started:
            break

        # 读取输出
        if process.stdout:
            line = process.stdout.readline()
            if line:
                print(f"  {line.strip()}")

    if not started:
        print("❌ 后端服务启动失败!")
        process.terminate()
        exit(1)

print("\n" + "=" * 70)
print("📜 等待并收集后端日志...")
print("=" * 70)

# 等待30秒收集日志
print("\n监听30秒后端日志...\n")
time.sleep(30)

print("\n" + "=" * 70)
print("📊 日志收集完成，现在检查项目状态")
print("=" * 70)

# 检查项目状态
import requests
project_id = "ab0dd81f-1d16-4bde-b60e-21295e58d7ed"

try:
    resp = requests.get(f"http://localhost:8000/api/v1/projects/{project_id}", timeout=10)
    if resp.status_code == 200:
        project = resp.json()
        print(f"\n项目名称: {project.get('name')}")
        print(f"项目状态: {project.get('status')}")
        print(f"项目进度: {project.get('progress', 0)}%")
    else:
        print(f"\n获取项目失败: {resp.status_code}")
except Exception as e:
    print(f"\n获取项目状态失败: {e}")

# 检查任务
try:
    resp = requests.get(f"http://localhost:8000/api/v1/tasks?project_id={project_id}", timeout=10)
    if resp.status_code == 200:
        tasks = resp.json()
        print(f"\n任务数: {len(tasks)}")
        for task in tasks:
            print(f"  任务: {task.get('name')}")
            print(f"  状态: {task.get('status')}")
            print(f"  进度: {task.get('progress', 0)}%")
            print(f"  当前步骤: {task.get('current_step', 'N/A')}")
            if task.get('error_message'):
                print(f"  ❌ 错误: {task.get('error_message')}")
except Exception as e:
    print(f"\n获取任务状态失败: {e}")

print("\n" + "=" * 70)