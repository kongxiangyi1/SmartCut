import requests
import json

# 获取项目详情
response = requests.get('http://localhost:8003/api/v1/projects/2a78084a-6197-43bc-b1c0-b89f41f603de')
data = response.json()

# 打印完整响应
print('=== 项目详情响应 ===')
print(json.dumps(data, ensure_ascii=False, indent=2))
