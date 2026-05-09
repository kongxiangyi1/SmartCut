
import sqlite3
import os

# 设置环境变量
os.environ['USE_SIMPLE_TASK_RUNNER'] = 'true'

# 连接数据库获取项目信息
conn = sqlite3.connect(r'e:\ClipProject\autoclip-main1\autoclip-main\data\autoclip.db')
cursor = conn.cursor()

cursor.execute("SELECT id, video_path FROM projects WHERE name LIKE '%clip_001_product%'")
project = cursor.fetchone()

if project:
    project_id = project[0]
    video_path = project[1]
    print(f'项目ID: {project_id}')
    print(f'视频路径: {video_path}')
    
    # 重置项目状态为 pending
    cursor.execute("UPDATE projects SET status = 'pending' WHERE id = ?", (project_id,))
    conn.commit()
    print('已重置项目状态为 pending')
    
else:
    print('未找到项目')

conn.close()

# 调用简化任务提交器启动处理
from backend.utils.simple_task_submitter import get_task_submitter

submitter = get_task_submitter()
result = submitter.submit_video_pipeline(
    project_id=project_id,
    input_video_path=video_path,
    input_srt_path=None
)

print(f'\n任务提交结果:')
print(f'成功: {result.get("success")}')
print(f'任务ID: {result.get("task_id")}')
print(f'状态: {result.get("status")}')
print(f'消息: {result.get("message")}')
