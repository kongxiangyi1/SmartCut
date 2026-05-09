
import sqlite3
conn = sqlite3.connect(r'e:\ClipProject\autoclip-main1\autoclip-main\data\autoclip.db')
cursor = conn.cursor()

print("=== 项目信息 ===")
cursor.execute("SELECT * FROM projects WHERE id = '7142000a-957a-4dcf-89e6-7c8a124bb8c3'")
project = cursor.fetchone()
if project:
    cols = [desc[0] for desc in cursor.description]
    for k, v in zip(cols, project):
        if k == 'raw_data' and isinstance(v, str):
            print(f"{k}: (raw data, {len(v)} chars)")
        else:
            print(f"{k}: {v}")

print("\n=== 任务记录 ===")
cursor.execute("SELECT * FROM tasks WHERE project_id = '7142000a-957a-4dcf-89e6-7c8a124bb8c3' ORDER BY created_at")
for task in cursor.fetchall():
    cols = [desc[0] for desc in cursor.description]
    print(dict(zip(cols, task)))

conn.close()
