#!/usr/bin/env python3

import sys
sys.path.append('.')

from backend.core.celery_app import celery_app
from backend.tasks.import_processing import process_import_task

def start_import_task(project_id, video_path):
    """手动启动导入任务"""
    print(f"🔄 手动启动导入任务...")
    print(f"   项目ID: {project_id}")
    print(f"   视频路径: {video_path}")
    
    try:
        # 提交Celery任务
        task = process_import_task.delay(project_id, video_path)
        
        print(f"✅ 任务已提交！")
        print(f"   任务ID: {task.id}")
        print(f"   状态: {task.status}")
        return task.id
        
    except Exception as e:
        print(f"❌ 任务提交失败: {e}")
        import traceback
        traceback.print_exc()
        return None

# 启动clip_001项目
project_id = "474e256d-bcd3-48a9-b6e5-8263ab1b8c40"
video_path = r"D:\Download\autoclip-main1\autoclip-main\data\projects\474e256d-bcd3-48a9-b6e5-8263ab1b8c40\raw\input.mp4"

task_id = start_import_task(project_id, video_path)

if task_id:
    print(f"\n🎯 任务已成功提交！")
    print(f"   可以监控任务执行状态")
    print(f"   处理预计需要10-30分钟（取决于视频长度）")
else:
    print(f"\n❌ 任务提交失败，需要检查worker状态")