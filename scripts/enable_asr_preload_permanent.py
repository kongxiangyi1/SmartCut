# -*- coding: UTF-8 -*-
"""
永久启用/禁用 ASR 模型预加载
修改 backend/main.py 文件
"""

import os
from pathlib import Path


def enable_preload():
    """启用预加载"""
    backend_main = Path("backend/main.py")
    
    if not backend_main.exists():
        print("❌ 文件不存在: backend/main.py")
        return False
    
    # 读取文件
    with open(backend_main, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查是否已经有设置
    if 'DISABLE_ASR_PRELOAD' in content and 'os.environ["DISABLE_ASR_PRELOAD"]' in content:
        # 替换为 false
        content = content.replace(
            'os.environ["DISABLE_ASR_PRELOAD"] = "true"',
            'os.environ["DISABLE_ASR_PRELOAD"] = "false"'
        )
        content = content.replace(
            "os.environ['DISABLE_ASR_PRELOAD'] = 'true'",
            "os.environ['DISABLE_ASR_PRELOAD'] = 'false'"
        )
        print("✅ 已修改为启用预加载")
    else:
        # 在 import 后面添加设置
        lines = content.split('\n')
        
        # 找到最后一个 import 语句
        last_import_idx = -1
        for i, line in enumerate(lines):
            if line.strip().startswith('import ') or line.strip().startswith('from '):
                last_import_idx = i
        
        # 在最后一个 import 后添加设置
        insert_idx = last_import_idx + 1
        setting_line = '\nos.environ["DISABLE_ASR_PRELOAD"] = "false"  # 启用 ASR 模型预加载'
        
        lines.insert(insert_idx, setting_line)
        content = '\n'.join(lines)
        print("✅ 已添加预加载配置（启用）")
    
    # 写回文件
    with open(backend_main, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return True


def disable_preload():
    """禁用预加载"""
    backend_main = Path("backend/main.py")
    
    if not backend_main.exists():
        print("❌ 文件不存在: backend/main.py")
        return False
    
    # 读取文件
    with open(backend_main, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查是否已经有设置
    if 'DISABLE_ASR_PRELOAD' in content and 'os.environ["DISABLE_ASR_PRELOAD"]' in content:
        # 替换为 true
        content = content.replace(
            'os.environ["DISABLE_ASR_PRELOAD"] = "false"',
            'os.environ["DISABLE_ASR_PRELOAD"] = "true"'
        )
        content = content.replace(
            "os.environ['DISABLE_ASR_PRELOAD'] = 'false'",
            "os.environ['DISABLE_ASR_PRELOAD'] = 'true'"
        )
        print("✅ 已修改为禁用预加载")
    else:
        # 在 import 后面添加设置
        lines = content.split('\n')
        
        # 找到最后一个 import 语句
        last_import_idx = -1
        for i, line in enumerate(lines):
            if line.strip().startswith('import ') or line.strip().startswith('from '):
                last_import_idx = i
        
        # 在最后一个 import 后添加设置
        insert_idx = last_import_idx + 1
        setting_line = '\nos.environ["DISABLE_ASR_PRELOAD"] = "true"  # 禁用 ASR 模型预加载（加速启动 144秒）'
        
        lines.insert(insert_idx, setting_line)
        content = '\n'.join(lines)
        print("✅ 已添加预加载配置（禁用）")
    
    # 写回文件
    with open(backend_main, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return True


def main():
    print("=" * 60)
    print("ASR 模型预加载配置工具")
    print("=" * 60)
    print()
    print("1. 禁用预加载（启动加速 144秒）")
    print("2. 启用预加载（首次使用更快）")
    print("3. 退出")
    print()
    
    choice = input("请选择 (1/2/3): ").strip()
    
    if choice == "1":
        print("\n正在禁用预加载...")
        if disable_preload():
            print("\n✅ 禁用成功！")
            print("   启动时间: 144秒 → 3秒")
            print("   重启服务后生效")
    elif choice == "2":
        print("\n正在启用预加载...")
        if enable_preload():
            print("\n✅ 启用成功！")
            print("   启动时间: 3秒 → 144秒")
            print("   首次使用更快")
            print("   重启服务后生效")
    else:
        print("\n已取消")


if __name__ == "__main__":
    main()
