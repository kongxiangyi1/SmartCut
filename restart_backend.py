import psutil
import subprocess
import time
import sys

print("=" * 70)
print("重启后端服务")
print("=" * 70)

# 杀掉旧的后端进程
print("1. 查找并杀掉旧的后端进程...")
for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
    try:
        cmdline = proc.cmdline()
        if cmdline and ('uvicorn' in cmdline or 'backend' in str(cmdline)):
            print(f"   杀掉进程 {proc.pid}: {cmdline}")
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except psutil.TimeoutExpired:
                proc.kill()
    except:
        pass

print("✓ 旧进程已清理")

# 等待几秒钟
time.sleep(2)

# 启动新的后端服务
print("\n2. 启动新的后端服务...")
BACKEND_DIR = r'e:\ClipProject\autoclip-main1\autoclip-main'

cmd = [
    sys.executable, '-m', 'uvicorn',
    'backend.main:app',
    '--host', '0.0.0.0',
    '--port', '8000',
    '--reload'
]

print(f"   命令: {' '.join(cmd)}")

# 启动进程
proc = subprocess.Popen(
    cmd,
    cwd=BACKEND_DIR,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True
)

print(f"   进程ID: {proc.pid}")

# 等待服务启动
print("\n3. 等待服务启动...")
max_wait = 30
for i in range(max_wait):
    print(f"   等待 {i+1}/{max_wait}...")
    time.sleep(1)
    
    # 检查端口
    port_running = False
    for conn in psutil.net_connections():
        if conn.laddr.port == 8000 and conn.status == 'LISTEN':
            port_running = True
            break
    
    if port_running:
        print("\n✓ 后端服务启动成功！")
        break

print("\n" + "=" * 70)
print("后端服务已重启！")
print("=" * 70)
