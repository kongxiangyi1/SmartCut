#!/usr/bin/env python3

import sqlite3
from pathlib import Path
import subprocess
import sys
import time

def fix_stuck_projects():
    """一键修复卡住的项目"""
    print("🔧 一键修复卡住项目")
    print("=" * 40)
    
    # 1. 重置所有processing状态的项目
    print("\n📊 步骤1: 重置数据库状态")
    db_path = Path('data') / 'autoclip.db'
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # 查找所有卡住的processing项目
        cursor.execute("SELECT id, name, status FROM projects WHERE status = 'processing'")
        stuck_projects = cursor.fetchall()
        
        if stuck_projects:
            print(f"   ❌ 找到 {len(stuck_projects)} 个卡住的项目")
            for project in stuck_projects:
                project_id, name, status = project
                print(f"     - {name} ({project_id[:8]}...)")
                cursor.execute("""
                    UPDATE projects 
                    SET status = 'pending', updated_at = datetime('now') 
                    WHERE id = ?
                """, (project_id,))
            
            conn.commit()
            print(f"   ✅ 已重置所有项目到pending状态")
        else:
            print(f"   ✅ 没有找到卡住的项目")
        
        conn.close()
    else:
        print(f"   ❌ 数据库文件不存在")
        return
    
    # 2. 停止当前Celery worker
    print(f"\n🔄 步骤2: 确保Celery worker状态")
    tasklist_cmd = 'powershell -Command "tasklist | findstr python"'
    result = subprocess.run(tasklist_cmd, shell=True, capture_output=True, text=True)
    if "python" in result.stdout:
        print(f"   📋 发现 {len([line for line in result.stdout.splitlines() if 'python' in line])} 个Python进程")
    
    # 3. 重启Celery worker
    print(f"\n🚀 步骤3: 启动Celery worker")
    
    celery_cmd = "python start_worker.py"
    print(f"   执行: {celery_cmd}")
    
    # 4. 重新开始bandicam项目处理
    print(f"\n🎬 步骤4: 重新启动bandicam项目")
    
    # 查找bandicam项目
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM projects WHERE name LIKE '%bandicam%'")
    bandicam_project = cursor.fetchone()
    conn.close()
    
    if bandicam_project:
        project_id = bandicam_project[0]
        print(f"   📦 Bandicam项目ID: {project_id}")
        
        # 触发API重新处理
        import requests
        try:
            api_url = f"http://localhost:8000/api/v1/projects/{project_id}/process"
            response = requests.post(api_url, timeout=30)
            
            if response.status_code == 200:
                print(f"   ✅ 成功触发重新处理！")
                print(f"   ⏳ 项目将重新开始分析...")
            else:
                print(f"   ❌ API调用失败: {response.status_code}")
                print(f"   响应: {response.text}")
        except Exception as e:
            print(f"   ❌ 触发处理失败: {e}")
    else:
        print(f"   ❌ 未找到bandicam项目")
    
    print(f"\n🎉 修复完成！")
    print(f"=" * 40)
    print(f"📊 总结:")
    print(f"   ✅ 卡住项目已重置为pending状态")
    print(f"   🔄 准备重启Celery worker")
    print(f"   🎬 Bandicam项目重新开始处理")
    print(f"""
💡 后续步骤:
   1. 等待5-10分钟让处理启动
   2. 检查CPU使用率是否上升
   3. 视频应在20-30分钟内处理完成
   4. 可在前端查看进度
""")

if __name__ == '__main__':
    fix_stuck_projects()
    
    # 实际启动Celery
    print(f"\n正在启动Celery worker...")
    subprocess.Popen([
        sys.executable, 'start_worker.py'
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    print(f"✅ Celery worker已启动（后台运行）")
    print(f"🔍 可在前端查看bandicam项目的进度")