import sys
sys.path.append('.')

from backend.core.celery_app import celery_app
from backend.tasks.import_processing import process_import_task

try:
    print(f"手动提交Celery任务...")
    print(f"项目ID: 99b6d221-145c-4d62-8560-df10b001645d")
    
    # 手动提交任务
    video_path = r'D:\Download\autoclip-main1\autoclip-main\data\projects\99b6d221-145c-4d62-8560-df10b001645d\raw\input.mp4'
    task = process_import_task.delay('99b6d221-145c-4d62-8560-df10b001645d', video_path)
    
    print(f"✅ 任务已提交!")
    print(f"任务ID: {task.id}")
    print(f"任务状态: {task.status}")
    
except Exception as e:
    print(f"❌ 提交任务失败: {e}")
    import traceback
    traceback.print_exc()