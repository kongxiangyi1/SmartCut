import requests
import json

# 检查项目状态
response = requests.get("http://localhost:8000/api/v1/projects/")
data = response.json()

print("=== 项目处理状态 ===\n")

for project in data['items']:
    print(f"项目ID: {project['id']}")
    print(f"名称: {project['name'][:50]}...")
    print(f"状态: {project['status']}")
    print(f"类型: {project['project_type']}")
    print(f"创建时间: {project['created_at']}")
    print(f"更新时间: {project['updated_at']}")
    print(f"片段数: {project['total_clips']}")
    print(f"合集数: {project['total_collections']}")
    print("---")

# 检查是否有处理中的项目
processing_projects = [p for p in data['items'] if p['status'] in ['processing']]
if processing_projects:
    print(f"\n🔄 正在处理 {len(processing_projects)} 个项目:")
    for project in processing_projects:
        print(f"- {project['name'][:30]}... (ID: {project['id']})")
else:
    print(f"\n✅ 当前没有项目正在处理中")

pending_projects = [p for p in data['items'] if p['status'] in ['pending']]
if pending_projects:
    print(f"\n⏳ 等待处理 {len(pending_projects)} 个项目:")
    for project in pending_projects:
        print(f"- {project['name'][:30]}... (ID: {project['id']})")