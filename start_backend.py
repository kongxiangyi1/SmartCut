import psutil
import subprocess
import time

print("=" * 60)
print("🔍 检查后端服务状态")
print("=" * 60)

# 检查端口8000
port_8000_running = False
for conn in psutil.net_connections():
    if conn.laddr.port == 8000 and conn.status == 'LISTEN':
        port_8000_running = True
        break

if port_8000_running:
    print("✅ 后端服务正在运行 (端口8000)")
else:
    print("❌ 后端服务未运行，尝试启动...")
    
    # 启动后端服务
    try:
        cmd = [
            "python", "-m", "uvicorn", 
            "backend.main:app", 
            "--host", "0.0.0.0", 
            "--port", "8000",
            "--reload"
        ]
        
        print(f"启动命令: {' '.join(cmd)}")
        process = subprocess.Popen(
            cmd,
            cwd=r'e:\ClipProject\autoclip-main1\autoclip-main',
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        # 等待服务启动
        print("\n等待服务启动...")
        for i in range(10):
            time.sleep(2)
            # 检查端口是否被监听
            port_ready = False
            for conn in psutil.net_connections():
                if conn.laddr.port == 8000 and conn.status == 'LISTEN':
                    port_ready = True
                    break
            if port_ready:
                print("✅ 后端服务启动成功!")
                break
            # 读取一些输出
            if process.stdout:
                lines = process.stdout.readline()
                if lines:
                    print(f"日志: {lines.strip()}")
        
        # 打印启动日志
        print("\n" + "=" * 60)
        print("📜 后端启动日志")
        print("=" * 60)
        if process.stdout:
            for _ in range(20):
                line = process.stdout.readline()
                if line:
                    print(line.strip())
                else:
                    break
        
    except Exception as e:
        print(f"❌ 启动失败: {e}")