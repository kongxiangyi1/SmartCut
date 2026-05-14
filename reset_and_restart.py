import sqlite3
import requests

BASE_URL = "http://localhost:8000"
project_id = "52cda853-3698-4fc3-820e-b62464d7f174"

print("=" * 70)
print("重置项目状态")
print("=" * 70)

# 1. 重置数据库中的项目和任务状态
conn = sqlite3.connect(r'e:\ClipProject\autoclip-main1\autoclip-main\data\autoclip.db')
cursor = conn.cursor()

# 重置项目状态为 pending
cursor.execute("UPDATE projects SET status = 'pending', completed_at = NULL WHERE id = ?", (project_id,))

# 删除旧的任务
cursor.execute("DELETE FROM tasks WHERE project_id = ?", (project_id,))

conn.commit()
conn.close()

print("✓ 项目状态已重置为 pending")
print("✓ 旧任务已删除")

print("\n" + "=" * 70)
print("重新触发处理")
print("=" * 70)

# 2. 重新触发处理
resp = requests.post(f"{BASE_URL}/api/v1/projects/{project_id}/process", timeout=30)
print(f"响应状态: {resp.status_code}")
print(f"响应内容: {resp.text}")

print("\n" + "=" * 70)
print("处理已开始")
print("=" * 70)
