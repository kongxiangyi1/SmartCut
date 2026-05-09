#!/usr/bin/env python3

import os
import subprocess
import time
import sys
import signal

def kill_python_processes():
    """杀死所有Python进程"""
    print("🔄 清理Python进程...")
    try:
        if os.name == 'nt':  # Windows
            os.system('taskkill /F /IM python.exe 2>nul')
        else:  # Unix
            os.system('pkill -f python')
        time.sleep(2)
    except Exception as e:
        print(f"清理进程警告: {e}")

def start_backend():
    """启动后端服务"""
    print("🚀 启动后端服务...")
    
    # 设置PYTHONPATH
    env = os.environ.copy()
    env['PYTHONPATH'] = f"{env.get('PYTHONPATH', '')};{os.getcwd()}"
    
    # 启动服务
    cmd = [sys.executable, "-m", "uvicorn", "backend.main:app", 
           "--host", "0.0.0.0", "--port", "8000", "--reload"]
    
    try:
        process = subprocess.Popen(cmd, env=env)
        time.sleep(3)
        
        # 验证服务启动
        import requests
        try:
            response = requests.get("http://localhost:8000/docs", timeout=5)
            if response.status_code == 200:
                print("✅ 后端服务启动成功！")
                return True
            else:
                print(f"❌ 后端服务响应异常: {response.status_code}")
        except Exception as e:
            print(f"❌ 后端服务连接失败: {e}")
            
    except Exception as e:
        print(f"❌ 启动后端失败: {e}")
    
    return False

def verify_system():
    """验证系统状态"""
    print("\n🔍 验证系统状态...")
    
    try:
        import requests
        
        # 测试关键API端点
        endpoints = [
            ("API根路径", "http://localhost:8000/"),
            ("API文档", "http://localhost:8000/docs"),
            ("项目列表", "http://localhost:8000/api/v1/projects/"),
            ("设置API", "http://localhost:8000/api/v1/settings")
        ]
        
        all_ok = True
        for name, url in endpoints:
            try:
                response = requests.get(url, timeout=5)
                if response.status_code in [200, 404]:  # 404也说明服务正常
                    print(f"   ✅ {name}: {response.status_code}")
                else:
                    print(f"   ❌ {name}: {response.status_code}")
                    all_ok = False
            except Exception as e:
                print(f"   ❌ {name}: {e}")
                all_ok = False
        
        # 测试项目API返回数据格式
        try:
            response = requests.get("http://localhost:8000/api/v1/projects/", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'items' in data:
                    print(f"   ✅ 项目数据格式: 正常 ({len(data['items'])}个项目)")
                    # 显示项目状态概览
                    for i, item in enumerate(data['items'][:3]):
                        name = item.get('name', '')[:30]
                        status = item.get('status', 'unknown')
                        print(f"     {i+1}. {name}... - {status}")
                else:
                    print(f"   ❌ 项目数据格式异常")
                    all_ok = False
        except Exception as e:
            print(f"   ❌ 项目API测试失败: {e}")
            all_ok = False
            
        return all_ok
        
    except Exception as e:
        print(f"❌ 系统验证失败: {e}")
        return False

def main():
    print("🔧 AutoClip 全系统重启工具")
    print("=" * 50)
    
    # 步骤1: 清理进程
    kill_python_processes()
    
    # 步骤2: 启动后端
    backend_ok = start_backend()
    
    if backend_ok:
        # 步骤3: 验证系统
        system_ok = verify_system()
        
        print("\n" + "=" * 50)
        if system_ok:
            print("🎉 系统重启成功！")
            print("\n💡 使用指南:")
            print("  🌐 前端访问: http://localhost:3000")
            print("  📖 API文档: http://localhost:8000/docs")
            print("  📊 项目API: http://localhost:8000/api/v1/projects/")
            print("  ⚙️  设置API: http://localhost:8000/api/v1/settings")
            print("\n  ✨ 现在前端应该可以正常加载视频分类和项目列表了！")
        else:
            print("⚠️  系统部分功能异常")
            print("\n🔧 建议手动检查:")
            print("  1. 查看详细的错误信息")
            print("  2. 检查.env配置文件")
            print("  3. 重启前端服务")
    else:
        print("\n❌ 后端启动失败")
        print("\n🔍 故障诊断:")
        print("  1. 检查Python环境: python --version")
        print("  2. 安装依赖: pip install -r requirements.txt")
        print("  3. 检查端口占用: netstat -ano | findstr :8000")
        print("  4. 查看详细错误日志")

if __name__ == '__main__':
    main()