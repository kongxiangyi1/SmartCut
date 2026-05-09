import sqlite3
import os
db_path = 'data/autoclip.db'

if not os.path.exists(db_path):
    print(f'数据库文件不存在: {db_path}')
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print('检查项目表...')
cursor.execute('SELECT COUNT(*) as count FROM projects')
row_count = cursor.fetchone()[0]
print(f'项目表行数: {row_count}')

print('检查项目状态分布...')
cursor.execute('SELECT COUNT(*) as count, status FROM projects GROUP BY status')
for row in cursor.fetchall():
    print(f'  状态 {row[1]}: {row[0]} 项')

print('修复状态...')
cursor.execute("UPDATE projects SET status = 'pending' WHERE status = 'importing'")
fixed_count = cursor.rowcount
print(f'修复了 {fixed_count} 个项目')

conn.commit()
conn.close()
print('数据库修复完成！')