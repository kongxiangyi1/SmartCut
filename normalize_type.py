#!/usr/bin/env python3
import sqlite3

db_path = 'data/autoclip.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print('标准化project_type值...')

# 更新type为全小写
updates = [
    ("DEFAULT", "default"),
    ("KNOWLEDGE", "knowledge"),
    ("BUSINESS", "business"),
    ("OPINION", "opinion"),
]

for old_val, new_val in updates:
    cursor.execute("UPDATE projects SET project_type = ? WHERE project_type = ?", (new_val, old_val))
    count = cursor.rowcount
    if count > 0:
        print(f'已更新 {count} 个类型从 [{old_val}] 到 [{new_val}]')

conn.commit()
conn.close()
print('数据库类型标准化完成！')