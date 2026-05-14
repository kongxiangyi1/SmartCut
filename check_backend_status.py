import psutil

print("=" * 70)
print("检查后端服务状态")
print("=" * 70)

# 检查端口8000
port_running = False
for conn in psutil.net_connections():
    if conn.laddr.port == 8000 and conn.status == 'LISTEN':
        port_running = True
        break

if port_running:
    print("✅ 端口8000正在监听")
else:
    print("❌ 端口8000未在监听")

print("\n检查日志...")

import os
log_path = r'e:\ClipProject\autoclip-main1\autoclip-main\logs'
if os.path.exists(log_path):
    log_files = os.listdir(log_path)
    print(f"日志文件: {log_files}")
    
    for log_file in log_files:
        full_path = os.path.join(log_path, log_file)
        print(f"\n--- {log_file} ---")
        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
            # 只显示最后20行
            lines = f.readlines()
            for line in lines[-20:]:
                print(line.rstrip())

print("\n" + "=" * 70)
