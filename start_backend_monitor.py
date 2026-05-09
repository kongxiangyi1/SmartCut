#!/usr/bin/env python3

import os
import sys
import subprocess
import time

def start_backend_with_monitor():
    """启动后端并监控日志输出"""
    print("🚀 启动后端服务 (监控模式)")
    print("=" * 60)
    
    # 设置环境变量
    env = os.environ.copy()
    env['PYTHONPATH'] = f"{env.get('PYTHONPATH', '')};{os.getcwd()}"
    
    # 启动命令
    cmd = [sys.executable, "-m", "uvicorn", "backend.main:app", 
           "--host", "0.0.0.0", "--port", "8000", "--reload", "--log-level", "info"]
    
    try:
        # 使用PIPE捕获输出
        process = subprocess.Popen(
            cmd, 
            env=env,
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            universal_newlines=True,
            bufsize=1
        )
        
        print(f"📊 进程已启动 (PID: {process.pid})")
        print("\n📋 启动日志:")
        print("-" * 60)
        
        # 监控启动过程
        started_ok = False
        start_time = time.time()
        timeout = 30  # 30秒超时
        
        while process.poll() is None and (time.time() - start_time) < timeout:
            if process.stdout:
                line = process.stdout.readline()
                if line:
                    line = line.strip()
                    print(f"   {line}")
                    
                    # 检查启动成功的标志
                    if "Application startup complete" in line or "Uvicorn running on" in line:
                        started_ok = True
                        print("\n✅ 后端服务启动成功！")
                        break
                    elif "error" in line.lower() or "exception" in line.lower() or "failed" in line.lower():
                        print(f"\n❌ 检测到错误: {line}")
                        break
        
        if not started_ok:
            if process.poll() is not None:
                print(f"\n❌ 进程异常退出 (返回码: {process.poll()})")
            elif (time.time() - start_time) >= timeout:
                print(f"\n⏳ 启动超时 ({timeout}秒)，但可能仍在启动中")
                print("   可以打开新窗口测试API: curl http://localhost:8000/docs")
        
        # 测试API连接
        print("\n🔍 测试API连接...")
        try:
            import requests
            response = requests.get("http://localhost:8000/docs", timeout=5)
            if response.status_code == 200:
                print("✅ API文档访问正常")
                
                response = requests.get("http://localhost:8000/api/v1/projects/", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ 项目API正常 ({len(data.get('items', []))}个项目)")
                else:
                    print(f"❌ 项目API异常: {response.status_code}")
            else:
                print(f"❌ API文档异常: {response.status_code}")
                
        except Exception as e:
            print(f"❌ API测试失败: {e}")
        
        print("\n💡 前端现在应该能正常加载了！")
        print("   访问: http://localhost:3000")
        
        # 让进程继续运行一段时间
        print("\n保持后端运行 60秒...")
        try:
            process.wait(timeout=60)
        except subprocess.TimeoutExpired:
            process.terminate()
            print("\n⏰ 演示结束，停止后端进程")
        
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    start_backend_with_monitor()