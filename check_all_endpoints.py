import requests

# 测试所有可能的项目相关API端点
endpoints = [
    '/api/v1/projects',
    '/api/v1/projects/2a78084a-6197-43bc-b1c0-b89f41f603de',
    '/api/v1/clips?project_id=2a78084a-6197-43bc-b1c0-b89f41f603de',
]

for endpoint in endpoints:
    try:
        response = requests.get(f'http://localhost:8003{endpoint}')
        print(f'=== {endpoint} ===')
        print(f'状态码: {response.status_code}')
        data = response.json()
        if isinstance(data, dict):
            if 'clip_count' in data:
                print(f'clip_count: {data.get('clip_count')}')
            if 'total_clips' in data:
                print(f'total_clips: {data.get('total_clips')}')
            if 'items' in data:
                for item in data['items']:
                    if item.get('name') == 'clip_001_product_0s-708s':
                        print(f"项目 {item.get('name')}:")
                        print(f"  clip_count: {item.get('clip_count')}")
                        print(f"  total_clips: {item.get('total_clips')}")
        elif isinstance(data, list):
            print(f'返回列表长度: {len(data)}')
        print()
    except Exception as e:
        print(f'{endpoint} 失败: {e}')
        print()
