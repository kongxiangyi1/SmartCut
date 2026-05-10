#!/usr/bin/env python3
"""
日志查看脚本 - 用于查看AutoClip后台日志和任务进度

用法:
    python scripts/view_logs.py [选项]

选项:
    -h, --help          显示帮助信息
    -l, --log           查看最新日志文件
    -t, --task          查看任务状态
    -p, --project ID    查看指定项目的状态和日志
    -f, --follow        实时跟踪日志
    -s, --status        查看所有服务状态
"""

import argparse
import os
import sys
import time
from pathlib import Path

# 添加项目路径到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

def safe_print(msg):
    """安全打印，处理编码问题"""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('utf-8', errors='replace').decode('gbk', errors='replace'))

def get_log_files():
    """获取日志文件列表"""
    log_dir = Path(__file__).parent.parent / "logs"
    if not log_dir.exists():
        safe_print("日志目录不存在: {}".format(log_dir))
        return []
    
    log_files = sorted(log_dir.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
    return log_files

def tail_file(file_path, lines=50):
    """获取文件末尾的指定行数"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.readlines()
            return content[-lines:]
    except Exception as e:
        safe_print("读取文件失败: {}".format(e))
        return []

def follow_file(file_path):
    """实时跟踪文件内容"""
    safe_print("实时跟踪日志: {}".format(file_path))
    safe_print("=" * 80)
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            f.seek(0, os.SEEK_END)
            while True:
                line = f.readline()
                if line:
                    safe_print(line.rstrip())
                else:
                    time.sleep(1)
    except KeyboardInterrupt:
        safe_print("停止跟踪")
    except Exception as e:
        safe_print("跟踪失败: {}".format(e))

def show_task_status(project_id=None):
    """显示任务状态"""
    try:
        from backend.core.database import SessionLocal
        from backend.models.task import Task
        from backend.models.project import Project
        
        db = SessionLocal()
        
        if project_id:
            # 查看指定项目的任务
            tasks = db.query(Task).filter(Task.project_id == project_id).order_by(Task.created_at.desc()).all()
            project = db.query(Project).filter(Project.id == project_id).first()
            
            if project:
                safe_print("\n项目信息:")
                safe_print("   项目ID: {}".format(project.id))
                safe_print("   状态: {}".format(project.status))
                safe_print("   创建时间: {}".format(project.created_at))
                safe_print("   更新时间: {}".format(project.updated_at))
        else:
            # 查看最近的任务
            tasks = db.query(Task).order_by(Task.created_at.desc()).limit(10).all()
        
        if not tasks:
            safe_print("没有找到任务")
            return
        
        safe_print("\n任务列表 ({}个):".format(len(tasks)))
        safe_print("-" * 120)
        safe_print("{:<36} {:<36} {:<15} {:<8} {:<20}".format('任务ID', '项目ID', '状态', '进度', '步骤'))
        safe_print("-" * 120)
        
        for task in tasks:
            progress = "{}%".format(task.progress) if task.progress else "N/A"
            safe_print("{:<36} {}... {:<15} {:<8} {:<20}".format(task.id, task.project_id[:8], task.status.name, progress, task.current_step or 'N/A'))
            
            if task.error_message:
                safe_print("   错误: {}...".format(task.error_message[:100]))
        
        db.close()
        
    except Exception as e:
        safe_print("获取任务状态失败: {}".format(e))
        import traceback
        traceback.print_exc()

def show_service_status():
    """显示服务状态"""
    safe_print("服务状态检查:")
    
    # 检查后端服务
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', 8001))
        backend_status = "运行中" if result == 0 else "未运行"
        sock.close()
    except Exception:
        backend_status = "检查失败"
    
    # 检查前端服务
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', 3000))
        frontend_status = "运行中" if result == 0 else "未运行"
        sock.close()
    except Exception:
        frontend_status = "检查失败"
    
    # 检查Redis
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', 6379))
        redis_status = "运行中" if result == 0 else "未运行"
        sock.close()
    except Exception:
        redis_status = "检查失败"
    
    safe_print("   后端服务 (8001): {}".format(backend_status))
    safe_print("   前端服务 (3000): {}".format(frontend_status))
    safe_print("   Redis (6379): {}".format(redis_status))

def show_project_details(project_id):
    """显示项目详细信息"""
    safe_print("\n项目详情: {}".format(project_id))
    safe_print("=" * 80)
    
    # 显示项目目录结构
    project_dir = Path(__file__).parent.parent / "data" / "projects" / project_id
    if project_dir.exists():
        safe_print("\n项目目录结构:")
        for root, dirs, files in os.walk(project_dir):
            level = root.replace(str(project_dir), '').count(os.sep)
            indent = ' ' * 2 * level
            safe_print("{}{}/".format(indent, os.path.basename(root)))
            subindent = ' ' * 2 * (level + 1)
            for file in sorted(files):
                file_path = Path(root) / file
                size = file_path.stat().st_size
                safe_print("{}{} ({} bytes)".format(subindent, file, size))
    
    # 显示关键文件内容
    metadata_dir = project_dir / "metadata"
    if metadata_dir.exists():
        # 显示大纲文件
        outline_file = metadata_dir / "step1_outline.json"
        if outline_file.exists():
            safe_print("\n大纲内容:")
            content = tail_file(outline_file, 20)
            safe_print(''.join(content))
        
        # 显示时间线文件
        timeline_file = metadata_dir / "step2_timeline.json"
        if timeline_file.exists():
            safe_print("\n时间线内容:")
            content = tail_file(timeline_file, 20)
            safe_print(''.join(content))

def main():
    parser = argparse.ArgumentParser(description="AutoClip日志查看脚本")
    parser.add_argument('-l', '--log', action='store_true', help='查看最新日志')
    parser.add_argument('-t', '--task', action='store_true', help='查看任务状态')
    parser.add_argument('-p', '--project', type=str, help='查看指定项目')
    parser.add_argument('-f', '--follow', action='store_true', help='实时跟踪日志')
    parser.add_argument('-s', '--status', action='store_true', help='查看服务状态')
    
    args = parser.parse_args()
    
    # 如果没有指定参数，显示帮助
    if not any([args.log, args.task, args.project, args.follow, args.status]):
        parser.print_help()
        return
    
    # 显示服务状态
    if args.status:
        show_service_status()
    
    # 查看任务状态
    if args.task:
        show_task_status()
    
    # 查看指定项目
    if args.project:
        show_task_status(args.project)
        show_project_details(args.project)
    
    # 查看日志
    if args.log or args.follow:
        log_files = get_log_files()
        if not log_files:
            safe_print("没有找到日志文件")
            return
        
        latest_log = log_files[0]
        safe_print("\n最新日志文件: {}".format(latest_log))
        safe_print("=" * 80)
        
        if args.follow:
            follow_file(latest_log)
        else:
            lines = tail_file(latest_log, 100)
            safe_print(''.join(lines))

if __name__ == "__main__":
    main()