import sqlite3
import requests
import time

BASE_URL = "http://localhost:8000"
project_id = "52cda853-3698-4fc3-820e-b62464d7f174"

print("=" * 70)
print("重置项目状态并重新触发")
print("=" * 70)

# 1. 重置数据库中的项目和任务状态
conn = sqlite3.connect(r'e:\ClipProject\autoclip-main1\autoclip-main\data\autoclip.db')
cursor = conn.cursor()

# 重置项目状态为 pending
cursor.execute("UPDATE projects SET status = 'pending', completed_at = NULL WHERE id = ?", (project_id,))

# 删除旧的任务
cursor.execute("DELETE FROM tasks WHERE project_id = ?", (project_id,))

conn.commit()
conn.close()

print("✓ 项目状态已重置为 pending")
print("✓ 旧任务已删除")

print("\n" + "=" * 70)
print("重新触发处理")
print("=" * 70)

# 2. 重新触发处理
resp = requests.post(f"{BASE_URL}/api/v1/projects/{project_id}/process", timeout=30)
print(f"响应状态: {resp.status_code}")
print(f"响应内容: {resp.text}")

result = resp.json()
task_id = result.get('task_id')

print("\n" + "=" * 70)
print("处理已开始！")
print(f"项目ID: {project_id}")
print(f"任务ID: {task_id}")
print("=" * 70)

# 3. 跟踪处理进度
print("\n开始跟踪处理进度...\n")

max_checks = 100
for i in range(max_checks):
    elapsed = i * 5
    
    try:
        # 获取项目状态
        resp_project = requests.get(f"{BASE_URL}/api/v1/projects/{project_id}", timeout=10)
        
        if resp_project.status_code == 200:
            project = resp_project.json()
            project_status = project.get('status')
            
            # 获取任务状态（直接查询tasks列表）
            resp_tasks = requests.get(f"{BASE_URL}/api/v1/tasks?project_id={project_id}", timeout=10)
            task_status = "N/A"
            task_progress = 0.0
            current_step = "N/A"
            error_msg = None
            
            if resp_tasks.status_code == 200:
                tasks = resp_tasks.json()
                if tasks and len(tasks) > 0:
                    task = tasks[0]
                    task_status = task.get('status')
                    task_progress = task.get('progress', 0)
                    current_step = task.get('current_step', 'N/A')
                    error_msg = task.get('error_message')
            
            # 打印状态
            print(f"[{elapsed:3d}s] 项目:{project_status:10s} | 任务:{task_status:10s} | 进度:{task_progress:3.0f}% | 步骤:{current_step}")
            
            # 检查是否完成或失败
            if project_status == 'completed':
                print("\n" + "=" * 70)
                print("🎉 处理完成！")
                print("=" * 70)
                
                # 获取切片和合集
                resp_clips = requests.get(f"{BASE_URL}/api/v1/clips?project_id={project_id}", timeout=10)
                clips = []
                if resp_clips.status_code == 200:
                    clips_data = resp_clips.json()
                    clips = clips_data if isinstance(clips_data, list) else clips_data.get('items', [])
                    print(f"\n📌 生成切片数: {len(clips)}")
                    
                    # 显示前5个切片
                    for i_clip, clip in enumerate(clips[:5]):
                        print(f"   切片{i_clip+1}: {clip.get('title')} | {clip.get('duration')}秒")
                    if len(clips) > 5:
                        print(f"   ...还有 {len(clips)-5} 个切片")
                
                resp_collections = requests.get(f"{BASE_URL}/api/v1/collections?project_id={project_id}", timeout=10)
                collections = []
                if resp_collections.status_code == 200:
                    coll_data = resp_collections.json()
                    collections = coll_data if isinstance(coll_data, list) else coll_data.get('items', [])
                    print(f"📌 生成合集数: {len(collections)}")
                
                print("\n" + "=" * 70)
                break
            
            if project_status == 'failed':
                print("\n" + "=" * 70)
                print("❌ 处理失败！")
                print("=" * 70)
                
                if error_msg:
                    print(f"\n错误信息: {error_msg}")
                
                print("\n" + "=" * 70)
                break
                
    except Exception as e:
        print(f"[{elapsed:3d}s] 错误: {e}")
    
    time.sleep(5)

if i == max_checks - 1:
    print("\n" + "=" * 70)
    print("⏰ 跟踪超时（超过8分钟）")
    print("=" * 70)
