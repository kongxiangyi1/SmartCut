
import sqlite3

# 连接数据库
conn = sqlite3.connect(r'E:\ClipProject\autoclip-main1\autoclip-main\data\autoclip.db')
cursor = conn.cursor()

project_id = "c652da34-19b0-42b2-bda8-d1fa9fa09b7b"

# 重置项目状态
print(f"重置项目状态: {project_id}")
try:
    cursor.execute("UPDATE projects SET status = 'pending', completed_at = NULL WHERE id = ?", (project_id,))
    conn.commit()
except Exception as e:
    print(f"更新项目状态失败: {e}")

# 删除相关的切片和合集记录
try:
    cursor.execute("DELETE FROM clips WHERE project_id = ?", (project_id,))
    conn.commit()
except Exception as e:
    print(f"删除切片记录失败: {e}")

try:
    cursor.execute("DELETE FROM collections WHERE project_id = ?", (project_id,))
    conn.commit()
except Exception as e:
    print(f"删除合集记录失败: {e}")

# 删除任务记录
try:
    cursor.execute("DELETE FROM tasks WHERE project_id = ?", (project_id,))
    conn.commit()
except Exception as e:
    print(f"删除任务记录失败: {e}")

conn.close()

print("项目状态已重置")

# 触发处理
import requests
import json

url = f"http://localhost:8000/api/v1/projects/{project_id}/process"
headers = {"Content-Type": "application/json"}
data = {"callback_url": ""}

print(f"\n触发项目处理: {project_id}")
try:
    response = requests.post(url, headers=headers, data=json.dumps(data))
    print(f"响应状态码: {response.status_code}")
    print(f"响应内容: {response.text}")
except Exception as e:
    print(f"请求失败: {e}")
