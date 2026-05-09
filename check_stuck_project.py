#!/usr/bin/env python3

import requests
import sqlite3
import os
import sys
from pathlib import Path

def check_stuck_project():
    """检查卡住的bandicam项目"""
    print("🔍 bandicam项目卡住诊断")
    print("=" * 50)
    
    project_name = "bandicam 2026-04-18 09-35-27-013"
    print(f"🎯 诊断项目: {project_name}")
    print(f"⏰ 已处理时间: 约4小时 (应该20-30分钟)")
    
    try:
        # 获取项目信息
        response = requests.get("http://localhost:8000/api/v1/projects/", timeout=10)
        if response.status_code != 200:
            print(f"❌ API访问失败: {response.status_code}")
            return
        
        data = response.json()
        projects = data['items']
        
        # 找到bandicam项目
        bandicam_project = None
        for project in projects:
            if project_name in project['name']:
                bandicam_project = project
                break
        
        if not bandicam_project:
            print(f"❌ 未找到项目: {project_name}")
            return
        
        print(f"\n📊 项目详细信息:")
        print(f"   ID: {bandicam_project['id']}")
        print(f"   名称: {bandicam_project['name']}")
        print(f"   当前状态: {bandicam_project['status']}")
        print(f"   项目类型: {bandicam_project['project_type']}")
        print(f"   片段数量: {bandicam_project['total_clips']}")
        print(f"   合集数量: {bandicam_project['total_collections']}")
        
        # 分析更新时间和创建时间的时间差
        from datetime import datetime
        created_at = datetime.fromisoformat(bandicam_project['created_at'].replace('Z', '+00:00'))
        updated_at = datetime.fromisoformat(bandicam_project['updated_at'].replace('Z', '+00:00'))
        now = datetime.now()
        
        created_ago = now - created_at.replace(tzinfo=None)
        updated_ago = now - updated_at.replace(tzinfo=None)
        
        print(f"   🌱 创建于: {created_at.strftime('%Y-%m-%d %H:%M:%S')} ({created_ago.days * 24 + created_ago.seconds // 3600}小时前)")
        print(f"   🔄 最后更新: {updated_at.strftime('%Y-%m-%d %H:%M:%S')} ({updated_ago.days * 24 + updated_ago.seconds // 3600}小时前)")
        
        # 诊断问题
        print(f"\n🔬 问题分析:")
        
        status = bandicam_project['status']
        if status == 'processing':
            if updated_ago.seconds > 3600:  # 超过1小时
                print(f"   ❌ 项目卡在processing状态超过1小时！")
                print(f"   💡 可能原因: Celery worker卡住或任务失败")
            else:
                print(f"   ⏳ 项目仍在正常处理范围内")
        elif status == 'pending':
            print(f"   ⏳ 项目在等待队列中，正常")
        elif status == 'completed':
            print(f"   ✅ 项目已完成处理")
        elif status == 'failed':
            print(f"   ❌ 项目处理失败，需要重启")
        
        # 检查数据库中的详细状态
        print(f"\n🗄️  数据库检查:")
        db_path = Path('data') / 'autoclip.db'
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 查询项目详情
            project_id = bandicam_project['id']
            cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
            project_row = cursor.fetchone()
            
            if project_row:
                print(f"   ✅ 数据库记录存在")
                print(f"   视频路径: {project_row['video_path']}")
                print(f"   处理配置: {project_row['processing_config']}")
                
                # 检查任务记录
                cursor.execute("SELECT * FROM tasks WHERE project_id = ?", (project_id,))
                tasks = cursor.fetchall()
                
                if tasks:
                    print(f"   📋 相关任务 ({len(tasks)}个):")
                    for task in tasks:
                        task_type = task[2]
                        task_status = task[3]
                        created = task[6]
                        print(f"     - {task_type}: {task_status} (创建于: {created})")
                else:
                    print(f"   ⚠️  无相关任务记录")
            else:
                print(f"   ❌ 数据库记录不存在")
            
            conn.close()
        
        # 检查视频文件
        print(f"\n📁 文件检查:")
        project_dir = Path('data') / 'projects' / bandicam_project['id']
        if project_dir.exists():
            raw_dir = project_dir / 'raw'
            if raw_dir.exists():
                files = list(raw_dir.glob('*'))
                print(f"   ✅ Raw目录存在: {len(files)}文件")
                for f in files:
                    if f.is_file():
                        size_mb = f.stat().st_size / (1024*1024)
                        print(f"     - {f.name} ({size_mb:.1f} MB)")
            
            # 检查是否有输出
            output_dir = project_dir / 'output'
            if output_dir.exists():
                output_files = list(output_dir.rglob('*'))
                print(f"   📊 输出目录: {len(output_files)}文件/文件夹")
                if output_files:
                    for f in sorted(output_files):
                        if f.is_file():
                            size_mb = f.stat().st_size / (1024*1024)
                            print(f"     - {f.relative_to(output_dir)} ({size_mb:.1f} MB)")
            else:
                print(f"   🔄 无输出目录，处理可能未完成")
        else:
            print(f"   ❌ 项目目录不存在")
        
        # 给出修复建议
        print(f"\n🔧 修复建议:")
        
        if status == 'processing' and updated_ago.seconds > 3600:
            print(f"   ❌ 项目明显卡住，建议:")
            print(f"      1. 将项目状态重置为pending")
            print(f"      2. 重启Celery worker")
            print(f"      3. 重新启动处理")
        elif status == 'processing':
            print(f"   ⏳ 项目可能仍在正常处理，建议:")
            print(f"      1. 继续等待")
            print(f"      2. 监控CPU/GPU使用率")
        else:
            print(f"   📊 项目状态正常")
        
    except Exception as e:
        print(f"❌ 诊断失败: {e}")
        import traceback
        traceback.print_exc()

def reset_stuck_project():
    """重置卡住的项目"""
    print("\n🔄 重置卡住项目")
    print("=" * 30)
    
    try:
        # 直接在数据库中重置项目状态
        db_path = Path('data') / 'autoclip.db'
        if not db_path.exists():
            print("❌ 数据库不存在")
            return
        
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # 查找bandicam项目
        cursor.execute("SELECT id, name, status FROM projects WHERE name LIKE ?", ("%bandicam%",))
        projects = cursor.fetchall()
        
        if projects:
            for project in projects:
                project_id, name, status = project
                if "processing" in status:
                    print(f"🔄 重置项目: {name}")
                    print(f"   从 '{status}' 改为 'pending'")
                    
                    cursor.execute("""
                        UPDATE projects 
                        SET status = ?, updated_at = datetime('now')
                        WHERE id = ?
                    """, ('pending', project_id))
                    
                    print(f"   ✅ 已重置成功！")
            
            conn.commit()
        else:
            print("❌ 未找到bandicam项目")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ 重置失败: {e}")

if __name__ == '__main__':
    check_stuck_project()
    
    print("\n" + "=" * 50)
    print("💡 选择下一步操作:")
    print("1. 按Enter键重置卡住的项目")
    print("2. 输入其他键退出")
    
    choice = input("> ").strip()
    if choice == "":
        reset_stuck_project()