"""
创建测试项目并提交处理任务
"""
import os
import sys

os.environ['USE_SIMPLE_TASK_RUNNER'] = 'true'
os.environ['PYTHONPATH'] = r'e:\ClipProject\autoclip-main1\autoclip-main'

from pathlib import Path
from backend.core.database import SessionLocal
from backend.models.project import Project, ProjectStatus, ProjectType
from backend.utils.simple_task_submitter import get_task_submitter
import uuid
from datetime import datetime

# 测试视频路径
VIDEO_PATH = r'E:\直播切片项目\output\20260420_新录制\clip_001_product_0s-708s.mp4'

def create_test_project():
    """创建测试项目"""
    db = SessionLocal()
    try:
        project_id = str(uuid.uuid4())

        # 复制视频到项目目录
        source_video = Path(VIDEO_PATH)
        project_dir = Path(f'e:/ClipProject/autoclip-main1/autoclip-main/data/projects/{project_id}')
        raw_dir = project_dir / 'raw'
        raw_dir.mkdir(parents=True, exist_ok=True)

        dest_video = raw_dir / 'input.mp4'

        print(f"复制视频到: {dest_video}")
        import shutil
        shutil.copy2(source_video, dest_video)
        print(f"视频复制完成: {dest_video.exists()}")

        # 创建项目记录
        project = Project(
            id=project_id,
            name='test_clip_001_product',
            description='测试视频处理流水线',
            project_type=ProjectType.KNOWLEDGE,
            status=ProjectStatus.PENDING,
            video_path=str(dest_video),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        db.add(project)
        db.commit()

        print(f"项目创建成功: {project_id}")
        return project_id

    except Exception as e:
        print(f"创建项目失败: {e}")
        db.rollback()
        return None
    finally:
        db.close()

def submit_processing_task(project_id):
    """提交处理任务"""
    print(f"\n提交处理任务: {project_id}")
    submitter = get_task_submitter()
    result = submitter.submit_video_pipeline(
        project_id=project_id,
        input_video_path=VIDEO_PATH,
        input_srt_path=None
    )
    print(f"提交结果: {result}")
    return result

def main():
    print("=" * 60)
    print("创建测试项目并提交处理任务")
    print("=" * 60)

    # 1. 创建项目
    project_id = create_test_project()
    if not project_id:
        return

    # 2. 提交处理任务
    result = submit_processing_task(project_id)

    print("\n" + "=" * 60)
    print("测试任务已提交")
    print(f"项目ID: {project_id}")
    print("请监控日志查看处理进度...")
    print("=" * 60)

if __name__ == "__main__":
    main()
