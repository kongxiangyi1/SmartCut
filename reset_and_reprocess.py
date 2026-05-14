import sqlite3
import requests
import json
import shutil
from pathlib import Path

project_id = 'b0d4c113-3a61-4df7-a7f0-cc03759c3dc6'
db_path = r'E:\ClipProject\autoclip-main1\autoclip-main\data\autoclip.db'
clips_dir = Path(r'E:\ClipProject\autoclip-main1\autoclip-main\data\projects\b0d4c113-3a61-4df7-a7f0-cc03759c3dc6\output\clips')
metadata_dir = Path(r'E:\ClipProject\autoclip-main1\autoclip-main\data\projects\b0d4c113-3a61-4df7-a7f0-cc03759c3dc6\metadata')

# 删除旧切片
if clips_dir.exists():
    shutil.rmtree(clips_dir)
    print(f'已删除旧切片目录: {clips_dir}')

# 删除旧元数据
if metadata_dir.exists():
    shutil.rmtree(metadata_dir)
    print(f'已删除旧元数据目录: {metadata_dir}')

# 重置项目状态
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute('UPDATE projects SET status = "pending" WHERE id = ?', (project_id,))
cursor.execute('DELETE FROM clips WHERE project_id = ?', (project_id,))
conn.commit()
conn.close()
print('项目状态已重置')

# 触发处理
url = 'http://localhost:8000/api/v1/projects/' + project_id + '/process'
headers = {'Content-Type': 'application/json'}
data = {'callback_url': ''}

print('触发项目处理...')
try:
    response = requests.post(url, headers=headers, data=json.dumps(data), timeout=60)
    print(f'状态码: {response.status_code}')
    print(f'响应: {response.text}')
except Exception as e:
    print(f'失败: {e}')
