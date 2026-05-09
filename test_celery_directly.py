import sys
sys.path.append('.')

from backend.core.celery_app import celery_app
from backend.services.project_service import ProjectService
from backend.core.database import get_db

try:
    # 检查项目存在
    db = next(get_db())
    project_service = ProjectService(db)
    
    project = project_service.get('99b6d221-145c-4d62-8560-df10b001645d')
    if project:
        print(f"找到项目: {project.name}")
        print(f"状态: {project.status}")
        print(f"视频路径: {project.video_path}")
        
        # 尝试手动提交任务
        from backend.tasks.import_processing import process_import_task
        print(f"准备提交处理任务...")
        
        # 检查视频文件是否存在
        import os
        if project.video_path and os.path.exists(project.video_path):
            print(f"✅ 视频文件存在: {project.video_path}")
            print(f"文件大小: {os.path.getsize(project.video_path)} 字节")
        else:
            print(f"❌ 视频文件不存在: {project.video_path}")
            
    else:
        print("项目不存在")
        
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()