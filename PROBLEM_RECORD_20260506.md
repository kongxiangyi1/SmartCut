# 问题记录：项目删除后前端仍显示

## 📅 日期
2026年5月6日

## 📝 问题描述
项目 `clip_001_product_0s-708s` 的目录已被删除，但前端仍然显示该项目。

## 🔍 根本原因
前端显示的项目列表来自 **SQLite 数据库** (`data/autoclip.db`)，而不是：
- `projects.json` 文件（配置缓存）
- `data/projects/{project_id}/` 目录（项目文件）

删除项目时只删除了文件系统中的项目目录和 `projects.json` 中的记录，但数据库中的记录仍然存在。

## 🔧 解决方案
通过关闭外键约束后删除数据库中的项目记录：

```python
import sqlite3

conn = sqlite3.connect('data/autoclip.db')
conn.execute("PRAGMA foreign_keys = OFF;")
cursor = conn.cursor()
cursor.execute("DELETE FROM projects WHERE name = 'clip_001_product_0s-708s'")
conn.commit()
conn.close()
```

## ⚠️ 预防措施

### 1. 统一删除流程
确保删除项目时同时清理以下三个位置：
- ✅ 项目目录 (`data/projects/{project_id}/`)
- ✅ `projects.json` 文件
- ✅ SQLite 数据库 (`autoclip.db`)

### 2. 代码层面修复
建议修改后端的项目删除 API，确保删除操作覆盖所有数据存储位置。

### 3. 数据一致性检查
定期检查数据库记录与文件系统的一致性，清理孤立的数据库记录。

## 📁 相关文件
- `data/autoclip.db` - SQLite 数据库（项目主数据来源）
- `data/projects.json` - 项目列表缓存
- `data/projects/{project_id}/` - 项目实际文件目录

## 📌 要点总结
- 前端项目列表 **只从数据库读取**，不从文件系统或 JSON 文件读取
- 删除项目时必须 **同时清理数据库记录**
- 数据库有外键约束，删除前需检查或关闭约束