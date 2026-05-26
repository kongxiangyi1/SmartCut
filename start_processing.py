import requests
import time

project_id = "b01e17bf-ba3e-4137-a648-a1d89566a6c7"

print(f"=== 启动项目 {project_id} 处理流程 ===")

# 启动处理
r = requests.post(f'http://127.0.0.1:8090/api/v1/projects/{project_id}/process')
result = r.json()

print(f"启动结果: {result.get('message')}")
print(f"任务ID: {result.get('task_id')}")

# 等待5秒后检查状态
print("\n=== 等待5秒后检查处理状态 ===")
time.sleep(5)

# 检查处理状态
r = requests.get(f'http://127.0.0.1:8090/api/v1/projects/{project_id}/status')
status_data = r.json()

print(f"当前状态: {status_data.get('status')}")
print(f"当前步骤: {status_data.get('current_step')}/{status_data.get('total_steps')}")
print(f"步骤名称: {status_data.get('step_name')}")
print(f"进度: {status_data.get('progress')}%")
print(f"错误信息: {status_data.get('error_message')}")
