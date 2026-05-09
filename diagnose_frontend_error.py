#!/usr/bin/env python3

import requests
import sys
import os
from pathlib import Path

def test_backend_api():
    """测试后端API"""
    print("=== 后端API测试 ===")
    
    endpoints = [
        "http://localhost:8000/",
        "http://localhost:8000/docs", 
        "http://localhost:8000/api/v1/projects/",
        "http://localhost:8000/api/v1/settings"
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(endpoint, timeout=5)
            print(f"✅ {endpoint}: {response.status_code}")
            
            if endpoint.endswith('projects/') and response.status_code == 200:
                data = response.json()
                print(f"   项目数量: {len(data.get('items', []))}")
                for project in data.get('items', [])[:3]:
                    print(f"   - {project.get('name', '')[:30]}... ({project.get('status', 'unknown')})")
                    
        except Exception as e:
            print(f"❌ {endpoint}: {e}")
    
    print()

def test_frontend_service():
    """测试前端服务"""
    print("=== 前端服务测试 ===")
    
    try:
        response = requests.get("http://localhost:3000/", timeout=5)
        if response.status_code == 200:
            print("✅ 前端服务: 正常运行")
            print(f"   页面大小: {len(response.content)} 字节")
        else:
            print(f"❌ 前端服务: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ 前端服务连接失败: {e}")
    
    print()

def check_project_structure():
    """检查项目结构"""
    print("=== 项目结构检查 ===")
    
    workspace = Path('.')
    
    # 检查关键目录
    key_dirs = [
        'backend',
        'frontend', 
        'data',
        'backend/api/v1',
        'backend/services'
    ]
    
    for dir_name in key_dirs:
        dir_path = workspace / dir_name
        if dir_path.exists():
            files = list(dir_path.glob('*'))
            print(f"✅ {dir_name}: {len(files)} 个文件")
        else:
            print(f"❌ {dir_name}: 目录不存在")
    
    print()

def check_database():
    """检查数据库状态"""
    print("=== 数据库检查 ===")
    
    db_path = Path('data') / 'autoclip.db'
    if db_path.exists():
        size_mb = db_path.stat().st_size / (1024*1024)
        print(f"✅ 数据库存在: {size_mb:.1f} MB")
        
        # 快速查询项目数量
        try:
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM projects")
            count = cursor.fetchone()[0]
            print(f"✅ 项目总数: {count}")
            conn.close()
        except Exception as e:
            print(f"❌ 数据库查询失败: {e}")
    else:
        print(f"❌ 数据库不存在: {db_path}")
    
    print()

def check_processes():
    """检查运行中的进程"""
    print("=== 进程检查 ===")
    
    # 检查Python进程
    import subprocess
    try:
        result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq python.exe'], 
                              capture_output=True, text=True)
        python_processes = [line for line in result.stdout.split('\n') if 'python.exe' in line]
        print(f"ℹ️ Python进程: {len(python_processes)} 个")
        for proc in python_processes[:3]:
            print(f"   {proc.strip()}")
    except Exception as e:
        print(f"❌ 进程检查失败: {e}")
    
    print()

def main():
    print("🔧 前端报错诊断工具")
    print("=" * 50)
    
    try:
        test_backend_api()
        test_frontend_service() 
        check_project_structure()
        check_database()
        check_processes()
        
        print("=== 诊断总结 ===")
        print("常见前端报错原因:")
        print("1. 🔴 后端API服务未启动")
        print("2. 🔴 前端服务崩溃")
        print("3. 🔴 API返回数据格式错误")
        print("4. 🔴 CORS跨域配置问题")
        print("5. 🔴 浏览器缓存问题")
        
    except Exception as e:
        print(f"❌ 诊断工具运行失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()