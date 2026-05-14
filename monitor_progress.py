
import requests
import time

project_id = "4402fd35-e134-45a4-81d7-a2440b562a8d"
url = f"http://localhost:8000/api/v1/projects/{project_id}"

print(f"开始监控项目处理进度: {project_id}")
print("-" * 60)

for i in range(30):  # 监控30次，每次间隔10秒
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            status = data.get('status', 'unknown')
            print(f"[{time.strftime('%H:%M:%S')}] 状态: {status}")
            
            if status in ['completed', 'failed']:
                print(f"处理完成！最终状态: {status}")
                break
        else:
            print(f"[{time.strftime('%H:%M:%S')}] 请求失败，状态码: {response.status_code}")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] 请求异常: {e}")
    
    time.sleep(10)

print("监控结束")
