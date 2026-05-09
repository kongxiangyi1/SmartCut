import requests
import json

try:
    response = requests.get("http://localhost:8000/api/v1/projects/", timeout=10)
    data = response.json()
    
    for project in data['items']:
        if project['id'] == '99b6d221-145c-4d62-8560-df10b001645d':
            print(f"项目状态: {project['status']}")
            print(f"更新时间: {project['updated_at']}")
            print(f"片段数: {project['total_clips']}")
            if project['status'] == 'pending':
                print("⏳ 等待处理")
            elif project['status'] == 'processing':
                print("🔄 正在处理")
            elif project['status'] == 'completed':
                print("✅ 处理完成")
            break
    else:
        print("项目未找到")
        
except Exception as e:
    print(f"检查失败: {e}")