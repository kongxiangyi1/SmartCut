import sqlite3
db_path = 'data/autoclip.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print('原始值檢查...')
cursor.execute('SELECT status FROM projects WHERE status IS NOT NULL')
rows = cursor.fetchall()
for i, row in enumerate(rows):
    val = row[0]
    print(f'[{i}] 值: [{val}], 长度: {len(val)}, ASCII: {[ord(c) for c in val]}')

conn.close()