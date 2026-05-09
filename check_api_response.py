import requests
import json

# 获取API响应
response = requests.get("http://localhost:8000/api/v1/projects/?page=1&page_size=1")
data = response.json()

# 检查第一个项目的大小
project = data['items'][0]
print(f"项目ID: {project['id']}")
print(f"项目名称: {project['name'][:50]}...")

# 检查每个字段的大小
large_fields = {}
total_size = 0

for key, value in project.items():
    if value is not None:
        field_size = len(str(value))
        total_size += field_size
        print(f"{key}: {field_size} 字符")
        
        if field_size > 1000:  # 标记大于1KB的字段
            large_fields[key] = field_size
            print(f"  !!! 大字段 {key}: {value[:200]}..." if field_size > 200 else f"  值: {value}")

print(f"\n总数据大小: {total_size} 字符 ({total_size/1024:.1f} KB)")
print(f"大字段数量: {len(large_fields)}")

if large_fields:
    print("大字段: ", list(large_fields.keys()))