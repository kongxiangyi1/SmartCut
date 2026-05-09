#!/usr/bin/env python3
import requests
import json

url = 'http://localhost:8000/api/v1/projects/'

try:
    response = requests.get(url)
    print(f'Status Code: {response.status_code}')
    if response.status_code == 200:
        data = response.json()
        print('✅ API 调用成功')
        
        items = data.get('items', [])
        print(f'共 {len(items)} 个项目')
        
        for i, item in enumerate(items):
            print(f'  [{i+1}] {item["id"][:8]}... - {item["status"]} - {item.get("name", "")[:20]}...')
        
    else:
        print(f'❌ API 调用失败: {response.text}')
        
except Exception as e:
    print(f'❌ 请求异常: {e}')