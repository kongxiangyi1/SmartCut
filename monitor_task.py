import requests
import json
import time

BASE_URL = "http://localhost:8000"
project_id = "ab0dd81f-1d16-4bde-b60e-21295e58d7ed"

print("=" * 70)
print("🔄 持续检查任务状态 (按 Ctrl+C 停止)")
print("=" * 70)

try:
    while True:
        # 获取项目状态
        resp = requests.get(f"{BASE_URL}/api/v1/projects/{project_id}", timeout=10)
        if resp.status_code == 200:
            project = resp.json()
            proj_status = project.get('status')
            proj_progress = project.get('progress', 0)
            
            # 获取任务状态
            resp_tasks = requests.get(f"{BASE_URL}/api/v1/tasks?project_id={project_id}", timeout=10)
            if resp_tasks.status_code == 200:
                tasks = resp_tasks.json()
                if tasks:
                    task = tasks[0]
                    task_status = task.get('status')
                    task_progress = task.get('progress', 0)
                    current_step = task.get('current_step', 'N/A')
                    
                    print(f"\r项目状态: {proj_status:10s} | 项目进度: {proj_progress:3.0f}% | "
                          f"任务状态: {task_status:10s} | 任务进度: {task_progress:3.0f}% | "
                          f"当前步骤: {current_step}", end="")
                else:
                    print(f"\r项目状态: {proj_status:10s} | 项目进度: {proj_progress:3.0f}% | 无任务", end="")
        
        time.sleep(2)
        
except KeyboardInterrupt:
    print("\n\n检测到停止信号，退出监控")