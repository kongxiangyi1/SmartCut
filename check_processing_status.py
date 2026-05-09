import time
import requests
import json

def check_status():
    try:
        response = requests.get("http://localhost:8000/api/v1/projects/", timeout=5)
        data = response.json()
        
        # 找到ID为99b6d221-145c-4d62-8560-df10b001645d的项目（最近上传的）
        target_project = None
        for project in data['items']:
            if project['id'] == '99b6d221-145c-4d62-8560-df10b001645d':
                target_project = project
                break
        
        if target_project:
            print(f"📊 项目状态更新:")
            print(f"  名称: {target_project['name'][:30]}...")
            print(f"  状态: {target_project['status']}")
            print(f"  类型: {target_project['project_type']}")
            print(f"  更新时间: {target_project['updated_at']}")
            print(f"  片段数: {target_project['total_clips']}")
            
            if target_project['status'] == 'processing':
                print(f"  ✅ 项目正在处理中...")
            elif target_project['status'] == 'completed':
                print(f"  🎉 项目处理完成!")
            elif target_project['status'] == 'failed':
                print(f"  ❌ 项目处理失败")
            else:
                print(f"  ⏳ 项目等待处理中...")
        else:
            print("❌ 未找到目标项目")
            print("所有项目:")
            for project in data['items']:
                print(f"  - {project['id']}: {project['name'][:30]}... ({project['status']})")
                
    except Exception as e:
        print(f"🔴 检查状态失败: {e}")

print("监控处理进度...\n")
for i in range(5):
    check_status()
    time.sleep(2)
    print()