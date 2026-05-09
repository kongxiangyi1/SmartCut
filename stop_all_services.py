#!/usr/bin/env python3

import subprocess
import psutil
import signal
import os
import sys
from time import sleep

def stop_all_services():
    """停止所有AutoClip相关服务"""
    print("🛑 停止所有AutoClip服务")
    print("=" * 40)
    
    # 1. 停止Celery worker
    print(f"\n🧹 步骤1: 停止Celery worker")
    celery_found = False
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline', [])
            name = proc.info.get('name', '')
            pid = proc.info.get('pid', 0)
            
            if ('python' in name.lower() and 
                ('celery' in ' '.join(cmdline).lower() or 
                 'start_worker.py' in ' '.join(cmdline) or
                 'tasks.import_processing' in ' '.join(cmdline))):
                print(f"   🔴 停止Celery进程 PID {pid}: {' '.join(cmdline)}")
                proc.terminate()
                celery_found = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    if not celery_found:
        print("   ✅ 没有找到运行中的Celery worker")
    
    # 2. 停止FastAPI后端
    print(f"\n⚡ 步骤2: 停止FastAPI后端")
    backend_found = False
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline', [])
            name = proc.info.get('name', '')
            pid = proc.info.get('pid', 0)
            
            if ('python' in name.lower() and 
                ('uvicorn' in ' '.join(cmdline).lower() or 
                 'main.py' in ' '.join(cmdline) or
                 'backend.main' in ' '.join(cmdline))):
                print(f"   🔴 停止FastAPI进程 PID {pid}: {' '.join(cmdline)}")
                proc.terminate()
                backend_found = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    if not backend_found:
        print("   ✅ 没有找到运行中的FastAPI后端")
    
    # 3. 停止前端Vite服务
    print(f"\n🎨 步骤3: 停止前端服务")
    frontend_found = False
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline', [])
            name = proc.info.get('name', '')
            pid = proc.info.get('pid', 0)
            
            if ('node' in name.lower() and 
                ('vite' in ' '.join(cmdline).lower() or 
                 'dev --port 3000' in ' '.join(cmdline) or
                 'npm run dev' in ' '.join(cmdline))):
                print(f"   🔴 停止Node进程 PID {pid}: {' '.join(cmdline)}")
                proc.terminate()
                frontend_found = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    if not frontend_found:
        print("   ✅ 没有找到运行中的前端服务")
    
    # 4. 停止可能的Redis进程（如果本地有）
    print(f"\n🗃️  步骤4: 停止Redis（如存在）")
    redis_found = False
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline', [])
            name = proc.info.get('name', '')
            pid = proc.info.get('pid', 0)
            
            if ('redis' in name.lower() or 'redis' in ' '.join(cmdline).lower()):
                print(f"   🔴 停止Redis进程 PID {pid}: {' '.join(cmdline)}")
                proc.terminate()
                redis_found = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    if not redis_found:
        print("   ✅ 没有找到运行中的Redis服务")
    
    # 5. 等待进程退出
    sleep(2)
    
    # 6. 检查是否还有残留进程
    print(f"\n🔍 步骤5: 检查残留进程")
    remaining_python = []
    remaining_node = []
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline', [])
            name = proc.info.get('name', '')
            pid = proc.info.get('pid', 0)
            
            if ('python' in name.lower() and 
                any(keyword in ' '.join(cmdline).lower() for keyword in 
                    ['celery', 'uvicorn', 'main.py', 'autoclip'])):
                remaining_python.append((pid, cmdline))
            
            if ('node' in name.lower() and 
                any(keyword in ' '.join(cmdline).lower() for keyword in 
                    ['vite', 'autoclip'])):
                remaining_node.append((pid, cmdline))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    if remaining_python:
        print(f"   ⚠️  还有 {len(remaining_python)} 个Python进程未退出:")
        for pid, cmdline in remaining_python:
            print(f"     PID {pid}: {' '.join(cmdline)}")
            # 强制杀死
            try:
                subprocess.run(['taskkill', '/F', '/PID', str(pid)], 
                             capture_output=True, shell=True)
                print(f"     🔴 已强制停止PID {pid}")
            except Exception as e:
                print(f"     ❌ 停止PID {pid}失败: {e}")
    
    if remaining_node:
        print(f"   ⚠️  还有 {len(remaining_node)} 个Node进程未退出:")
        for pid, cmdline in remaining_node:
            print(f"     PID {pid}: {' '.join(cmdline)}")
            # 强制杀死
            try:
                subprocess.run(['taskkill', '/F', '/PID', str(pid)], 
                             capture_output=True, shell=True)
                print(f"     🔴 已强制停止PID {pid}")
            except Exception as e:
                print(f"     ❌ 停止PID {pid}失败: {e}")
    
    print(f"\n🎉 所有服务已停止！")
    print(f"=" * 40)
    print(f"📊 停止的服务:")
    if 'celery_found' in locals() and celery_found:
        print(f"   ✅ Celery worker (停止)")
    if 'backend_found' in locals() and backend_found:
        print(f"   ✅ FastAPI后端 (停止)")
    if 'frontend_found' in locals() and frontend_found:
        print(f"   ✅ 前端服务 (停止)")
    if 'redis_found' in locals() and redis_found:
        print(f"   ✅ Redis服务 (停止)")
    
    print(f"""
🟢 服务状态:
   - 🌐 前端: http://localhost:3000/ (不可访问)
   - ⚡ 后端: http://localhost:8000/ (不可访问)
   - 🔄 异步任务: 已停止
""")

if __name__ == '__main__':
    try:
        stop_all_services()
    except Exception as e:
        print(f"❌ 停止服务时出现错误: {e}")
        import traceback
        traceback.print_exc()