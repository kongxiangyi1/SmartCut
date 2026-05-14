import psutil
import time

print("=" * 70)
print("清理旧的后端进程")
print("=" * 70)

# 只杀掉监听8000或8001端口的进程
for conn in psutil.net_connections():
    if conn.laddr.port in (8000, 8001) and conn.status == 'LISTEN':
        try:
            proc = psutil.Process(conn.pid)
            print(f"   杀掉进程 {conn.pid}")
            proc.terminate()
            time.sleep(1)
            if proc.is_running():
                proc.kill()
        except:
            pass

print("\n✓ 清理完成")
print("\n请手动运行以下命令启动后端:")
print("   cd e:\\ClipProject\\autoclip-main1\\autoclip-main")
print("   python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload")
print("\n" + "=" * 70)
