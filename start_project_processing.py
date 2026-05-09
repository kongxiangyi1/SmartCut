import requests
import json

try:
    # 手动触发项目处理
    project_id = "99b6d221-145c-4d62-8560-df10b001645d"
    
    print(f"触发项目处理: {project_id}")
    
    response = requests.post(
        f"http://localhost:8000/api/v1/projects/{project_id}/process"
    )
    
    print(f"响应状态: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"处理已启动: {result.get('message', 'N/A')}")
        print(f"任务ID: {result.get('task_id', 'N/A')}")
        print(f"Celery任务ID: {result.get('celery_task_id', 'N/A')}")
    else:
        print(f"启动失败: {response.text}")
        
except Exception as e:
    print(f"错误: {e}")

    
# 检查更新后的状态
try:
    response = requests.get(f"http://localhost:8000/api/v1/projects/{project_id}")
    if response.status_code == 200:
        data = response.json()
        print(f"\n项目状态: {data.get('status', 'N/A')}")
        print(f"更新时间: {data.get('updated_at', 'N/A')}")
    else:
        print(f"获取项目详情失败: {response.status_code}")
except Exception as e:
    print(f"获取项目详情错误: {e}")