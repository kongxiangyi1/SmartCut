import sys
sys.path.append('.')

print("=== 当前系统状态检查 ===\n")

# 检查Celery worker状态
try:
    from backend.core.celery_app import celery_app
    from celery import current_app
    
    inspector = current_app.control.inspect()
    active = inspector.active()
    reserved = inspector.reserved()
    scheduled = inspector.scheduled()
    
    print("🔧 Celery Worker状态:")
    
    if active and len(active) > 0:
        print(f"  ✅ 活跃worker: {len(active)}")
        for worker, tasks in active.items():
            print(f"  📋 正在执行的任务 ({len(tasks)}):")
            for task in tasks:
                print(f"     - {task['name'][:50]}...")
                print(f"       任务ID: {task['id']}")
                print(f"       开始时间: {task['time_start']}")
    else:
        print("  ⏳ worker空闲，没有正在执行的任务")
        
    if reserved and len(reserved) > 0:
        print(f"  📥 等待处理的任务: {len(reserved)}")
        for worker, tasks in reserved.items():
            for task in tasks:
                print(f"     - {task['name'][:50]}...")
                
except Exception as e:
    print(f"❌ Celery检查失败: {e}")

print(f"\n📊 检查项目数据...")

# 检查项目数据
try:
    from backend.services.project_service import ProjectService
    from backend.core.database import get_db
    
    db = next(get_db())
    project_service = ProjectService(db)
    
    # 获取所有项目
    all_projects = project_service.get_projects_paginated({}, 1, 10)
    
    if hasattr(all_projects, 'items'):
        projects = all_projects.items
    else:
        projects = all_projects
        
    print(f"数据库中共有 {len(projects)} 个项目:")
    
    for i, project in enumerate(projects):
        # 获取基本属性
        project_id = str(getattr(project, 'id', ''))
        name = str(getattr(project, 'name', ''))[:40]
        status = str(getattr(project, 'status', ''))
        project_type = str(getattr(project, 'project_type', ''))
        
        print(f"  {i+1}. {name}...")
        print(f"     ID: {project_id[:8]}...")
        print(f"     状态: {status}")
        print(f"     类型: {project_type}")
        
        # 判断是否是导入中的项目
        if status in ['pending', 'processing']:
            print(f"     📌 正在处理中...")
            if status == 'pending':
                print(f"        💡 在队列中等待Celery worker处理")
            elif status == 'processing':
                print(f"        💡 正在被执行，可能在生成缩略图或字幕")
        print()
    
    db.close()
    
except Exception as e:
    print(f"❌ 项目查询失败: {e}")
    import traceback
    traceback.print_exc()

# 显示项目路径信息，帮助确认文件位置
print(f"\n📁 系统信息:")
import os
from pathlib import Path

workspace = Path('.')
print(f"  工作目录: {workspace.resolve()}")
print(f"  数据目录: {workspace / 'data'}")
if (workspace / 'data').exists():
    projects_dir = workspace / 'data' / 'projects'
    if projects_dir.exists():
        print(f"  项目目录: {projects_dir}")
        project_dirs = list(projects_dir.iterdir()) if projects_dir.exists() else []
        print(f"  项目文件夹数: {len(project_dirs)}")
        if project_dirs:
            # 显示最新的项目文件夹
            latest_dir = max(project_dirs, key=lambda p: p.stat().st_mtime)
            print(f"  最新项目文件夹: {latest_dir.name}")
            if latest_dir.is_dir():
                files = list(latest_dir.rglob('*')) if latest_dir.exists() else []
                videos = [f for f in files if f.suffix.lower() in ['.mp4', '.avi', '.mov']]
                print(f"  视频文件: {len(videos)}")
                if videos:
                    for video in videos[:3]:  # 最多显示3个
                        size_mb = video.stat().st_size / (1024*1024)
                        print(f"    - {video.name} ({size_mb:.1f} MB)")