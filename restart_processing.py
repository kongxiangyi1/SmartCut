
import sqlite3
import os
import shutil

# 设置环境变量
os.environ['USE_SIMPLE_TASK_RUNNER'] = 'true'

# 连接数据库获取项目信息
conn = sqlite3.connect(r'e:\ClipProject\autoclip-main1\autoclip-main\data\autoclip.db')
cursor = conn.cursor()

# 查找最新的项目
cursor.execute("SELECT id, name, video_path, status FROM projects ORDER BY created_at DESC LIMIT 5")
projects = cursor.fetchall()

print('=== 项目列表 ===')
for project in projects:
    print(f'{project[0][:8]}... | {project[1][:30]} | {project[3]}')

# 获取最新的项目
project = projects[0]
project_id = project[0]
video_path = project[2]
project_name = project[1]

print(f'\n=== 选择项目: {project_name} ===')
print(f'项目ID: {project_id}')
print(f'视频路径: {video_path}')

# 删除相关任务
cursor.execute("DELETE FROM tasks WHERE project_id = ?", (project_id,))
conn.commit()
print(f'已删除相关任务')

# 重置项目状态为 pending
cursor.execute("UPDATE projects SET status = 'pending' WHERE id = ?", (project_id,))
conn.commit()
print('已重置项目状态为 pending')

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
