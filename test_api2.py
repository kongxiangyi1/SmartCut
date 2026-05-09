#!/usr/bin/env python3
import urllib.request
import json
import sys

try:
    with urllib.request.urlopen('http://localhost:8000/api/v1/projects/') as response:
        if response.status == 200:
            data = json.loads(response.read().decode())
            print('✅ API 调用成功')
            
            items = data.get('items', [])
            print(f'共 {len(items)} 个项目')
            
            for i, item in enumerate(items):
                print(f'  [{i+1}] {item["id"][:8]}... - {item["status"]} - {item.get("name", "")[:20]}...')
        else:
            print(f'❌ 返回状态码: {response.status}')
            
except Exception as e:
    print(f'❌ 请求异常: {e}')