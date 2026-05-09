import requests
import json
from datetime import datetime

print("=== 最新上传项目检查 ===\n")

try:
    # 获取所有项目
    response = requests.get("http://localhost:8000/api/v1/projects/")
    data = response.json()
    
    # 按创建时间排序，找到最新项目
    projects = sorted(data['items'], key=lambda x: x['created_at'], reverse=True)
    
    print(f"📁 共有 {len(projects)} 个项目")
    
    if projects:
        latest = projects[0]
        print(f"\n🆕 最新项目:")
        print(f"  ID: {latest['id']}")
        print(f"  名称: {latest['name'][:50]}...")
        print(f"  状态: {latest['status']}")
        print(f"  类型: {latest['project_type']}")
        print(f"  创建时间: {latest['created_at']}")
        print(f"  更新时间: {latest['updated_at']}")
        print(f"  片段数: {latest['total_clips']}")
        print(f"  合集数: {latest['total_collections']}")
        
        # 根据状态给出不同提示
        status = latest['status']
        if status == 'pending':
            print(f"  ⏳ 状态: 等待处理中，Celery worker应该很快开始处理")
        elif status == 'processing':
            print(f"  🔄 状态: 正在处理，请等待AI分析完成")
        elif status == 'completed':
            print(f"  ✅ 状态: 处理完成，可以查看生成的片段和合集")
        elif status == 'failed':
            print(f"  ❌ 状态: 处理失败，请检查日志或重试")
            
        print(f"  🎯 缩略图: {'已生成' if latest['thumbnail'] else '无'}")
        
    else:
        print("❌ 没有找到任何项目")
        
    # 显示所有项目状态
    print(f"\n📊 所有项目状态:")
    for i, project in enumerate(projects):
        print(f"  {i+1}. {project['name'][:25]}... - {project['status']} ({project['id'][:8]}...)")
        
except Exception as e:
    print(f"🔴 检查失败: {e}")

# 检查是否还有活跃的处理任务
print(f"\n=== 处理监控 ===")
import sys
sys.path.append('.')

try:
    from backend.core.celery_app import celery_app
    from celery import current_app
    
    inspector = current_app.control.inspect()
    active = inspector.active()
    
    if active:
        print(f"✅ Celery worker活跃，正在处理 {len([t for tasks in active.values() for t in tasks])} 个任务")
    else:
        print(f"⏳ Celery worker空闲，等待任务")
        
except Exception as e:
    print(f"检查Celery状态失败: {e}")