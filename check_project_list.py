import requests

# 获取项目列表
response = requests.get('http://localhost:8003/api/v1/projects')
data = response.json()

# 检查返回结构
print('项目列表响应类型:', type(data).__name__)
if isinstance(data, dict):
    print('键:', list(data.keys()))
    if 'items' in data:
        for project in data['items']:
            print(f"项目: {project.get('name')}")
            print(f"  total_clips: {project.get('total_clips')}")
            print()
