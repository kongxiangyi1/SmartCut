#!/usr/bin/env python3
import sqlite3

db_path = 'data/autoclip.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print('标准化status值...')

# 更新status为全小写
updates = [
    ("COMPLETED", "completed"),
    ("PENDING", "pending"),
    ("PROCESSING", "processing"),
    ("FAILED", "failed"),
]

for old_val, new_val in updates:
    cursor.execute("UPDATE projects SET status = ? WHERE status = ?", (new_val, old_val))
    count = cursor.rowcount
    if count > 0:
        print(f'已更新 {count} 个状态从 [{old_val}] 到 [{new_val}]')

conn.commit()
conn.close()
print('数据库标准化完成！')