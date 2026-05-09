import requests
import time

print("测试后端API连接...")

# 测试后端是否能响应
for i in range(10):
    try:
        response = requests.get("http://localhost:8000/api/v1/projects/", timeout=5)
        print(f"✅ API连接成功！状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"项目数量: {len(data['items'])}")
            
            # 显示最新的项目
            for project in data['items'][:2]:
                print(f"\n项目: {project['name'][:30]}...")
                print(f"状态: {project['status']}")
                print(f"ID: {project['id'][:8]}...")
                print(f"片段: {project['total_clips']}, 合集: {project['total_collections']}")
                
        break
    except Exception as e:
        print(f"尝试 {i+1}/10 失败: {e}")
        if i < 9:
            time.sleep(2)
else:
    print("❌ 无法连接后端API")
    print("💡 建议手动启动后端: python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000")