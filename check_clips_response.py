import requests
import json

# 获取切片列表
response = requests.get('http://localhost:8003/api/v1/clips', params={'project_id': '2a78084a-6197-43bc-b1c0-b89f41f603de'})
data = response.json()

print('=== 切片列表响应 ===')
print(f'状态码: {response.status_code}')
print(f'键: {list(data.keys())}')
print(f'data[\"total\"]: {data.get('total')}')
print(f'data[\"pagination\"][\"total\"]: {data.get('pagination', {}).get('total')}')
print(f'data[\"items\"] 长度: {len(data.get('items', []))}')
print()

# 检查项目API中 clips 字段是否为空
response2 = requests.get('http://localhost:8003/api/v1/projects/2a78084a-6197-43bc-b1c0-b89f41f603de')
data2 = response2.json()
print('=== 项目详情中 clips 字段 ===')
print(f'clips 字段值: {data2.get('clips')}')
print(f'clips 类型: {type(data2.get('clips'))}')
