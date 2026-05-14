"""
测试视频处理流水线
"""
import os
import sys

# 设置环境变量
os.environ['USE_SIMPLE_TASK_RUNNER'] = 'true'
os.environ['PYTHONPATH'] = r'e:\ClipProject\autoclip-main1\autoclip-main'

from pathlib import Path
from backend.utils.simple_task_submitter import get_task_submitter
import sqlite3

# 测试视频路径
VIDEO_PATH = r'E:\直播切片项目\output\20260420_新录制\clip_001_product_0s-708s.mp4'

def check_project_status(project_id):
    """检查项目状态"""
    conn = sqlite3.connect(r'e:\ClipProject\autoclip-main1\autoclip-main\data\autoclip.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, status, created_at FROM projects WHERE id = ?', (project_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {'id': row[0], 'name': row[1], 'status': row[2], 'created_at': row[3]}
    return None

def main():
    print("=" * 60)
    print("视频处理流水线测试")
    print("=" * 60)

    # 1. 检查视频文件
    video_path = Path(VIDEO_PATH)
    print(f"\n[1] 检查视频文件: {video_path}")
    print(f"    存在: {video_path.exists()}")
    if video_path.exists():
        size_mb = video_path.stat().st_size / (1024 * 1024)
        print(f"    大小: {size_mb:.2f} MB")

    # 2. 检查数据库中是否有待处理项目
    print(f"\n[2] 检查数据库...")
    conn = sqlite3.connect(r'e:\ClipProject\autoclip-main1\autoclip-main\data\autoclip.db')
    cursor = conn.cursor()

    # 查找同名项目
    cursor.execute("SELECT id, name, status FROM projects WHERE name LIKE '%clip_001_product%' ORDER BY created_at DESC LIMIT 1")
    project = cursor.fetchone()
    conn.close()

    if project:
        project_id = project[0]
        project_name = project[1]
        project_status = project[2]
        print(f"    找到项目: {project_name}")
        print(f"    项目ID: {project_id}")
        print(f"    状态: {project_status}")

        # 如果项目状态是pending，提交处理任务
        if project_status == 'pending':
            print(f"\n[3] 提交处理任务...")
            submitter = get_task_submitter()
            result = submitter.submit_video_pipeline(
                project_id=project_id,
                input_video_path=str(video_path),
                input_srt_path=None
            )
            print(f"    提交结果: {result}")
            print(f"    成功: {result.get('success')}")
            print(f"    任务ID: {result.get('task_id')}")
            return project_id, result
        else:
            print(f"    项目状态不是pending，跳过提交")
            return project_id, None
    else:
        print("    未找到测试项目，需要先通过前端上传")
        return None, None

if __name__ == "__main__":
    project_id, result = main()
    if project_id:
        print(f"\n项目ID: {project_id}")
        print("请监控日志查看处理进度...")
