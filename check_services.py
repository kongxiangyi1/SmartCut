import psutil
import os

print("=" * 60)
print("🔍 检查后端服务状态")
print("=" * 60)

# 检查端口8000是否被占用
port_8000_found = False
port_3000_found = False

for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
    try:
        cmdline = proc.info.get('cmdline', [])
        pid = proc.info.get('pid')
        name = proc.info.get('name', '')

        cmdline_str = ' '.join(cmdline) if cmdline else ''

        # 检查是否有监听8000端口的进程
        for conn in psutil.net_connections():
            if conn.laddr.port == 8000 and conn.status == 'LISTEN':
                print(f"\n✅ 后端服务正在运行!")
                print(f"   PID: {pid}")
                print(f"   进程名: {name}")
                print(f"   命令行: {cmdline_str[:100]}...")
                port_8000_found = True

        # 检查是否有监听3000端口的进程（前端）
        for conn in psutil.net_connections():
            if conn.laddr.port == 3000 and conn.status == 'LISTEN':
                print(f"\n✅ 前端服务正在运行!")
                print(f"   PID: {pid}")
                print(f"   进程名: {name}")
                port_3000_found = True

    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        pass

if not port_8000_found:
    print("\n❌ 后端服务未运行 (端口8000)")

if not port_3000_found:
    print("❌ 前端服务未运行 (端口3000)")

print("\n" + "=" * 60)
print("📝 PID文件内容:")
print("=" * 60)

# 读取PID文件
try:
    with open(r'e:\ClipProject\autoclip-main1\autoclip-main\backend.pid', 'r') as f:
        backend_pid = f.read().strip()
        print(f"backend.pid: {backend_pid}")
except Exception as e:
    print(f"backend.pid: 无法读取 - {e}")

try:
    with open(r'e:\ClipProject\autoclip-main1\autoclip-main\frontend.pid', 'r') as f:
        frontend_pid = f.read().strip()
        print(f"frontend.pid: {frontend_pid}")
except Exception as e:
    print(f"frontend.pid: 无法读取 - {e}")

# 检查PID对应的进程是否真的存在
print("\n" + "=" * 60)
print("🔎 检查PID对应的进程:")
print("=" * 60)

for pid_str in [backend_pid, frontend_pid]:
    try:
        pid = int(pid_str)
        proc = psutil.Process(pid)
        print(f"\nPID {pid}:")
        print(f"  名称: {proc.name()}")
        print(f"  状态: {proc.status()}")
        cmdline = proc.cmdline()
        print(f"  命令: {' '.join(cmdline)[:100]}...")
    except psutil.NoSuchProcess:
        print(f"\nPID {pid_str}: 进程不存在!")
    except Exception as e:
        print(f"\nPID {pid_str}: {e}")