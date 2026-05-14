import requests
import time
import sys

BASE_URL = "http://localhost:8000"
project_id = "52cda853-3698-4fc3-820e-b62464d7f174"
task_id = "584d7d6d-2d74-4385-b783-c51412c472e1"

print("=" * 70)
print("📊 持续跟踪项目处理进度")
print("=" * 70)
print(f"项目ID: {project_id}")
print(f"任务ID: {task_id}")

# 跟踪最多100次（每次间隔5秒，总计约8分钟）
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
