# -*- coding: utf-8 -*-
import sqlite3

# 连接数据库
conn = sqlite3.connect('E:\\ClipProject\\autoclip-main1\\autoclip-main\\data\\autoclip.db')
cursor = conn.cursor()

# 获取所有表名
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

print('Tables found:')
for table in tables:
    table_name = table[0]
    print('  - %s' % table_name)
    # 清空表数据
    cursor.execute('DELETE FROM %s' % table_name)
    print('    OK')

# 提交更改并关闭连接
conn.commit()
conn.close()

print('\nDatabase data cleared successfully!')