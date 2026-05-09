#!/usr/bin/env python3
"""
快速检查API密钥配置
"""

from pathlib import Path
import os

def check_env_file():
    """检查.env文件配置"""
    env_file = Path(".env")
    if not env_file.exists():
        print("❌ .env文件不存在")
        return
        
    with open(env_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    api_key_line = None
    for i, line in enumerate(lines, 1):
        if line.startswith("API_DASHSCOPE_API_KEY="):
            api_key_line = (i, line.strip())
            break
    
    if api_key_line:
        line_num, content = api_key_line
        print(f"📄 .env文件第{line_num}行:")
        print(f"   {content}")
        
        # 检查密钥格式
        if "sk-" in content and len(content.split('"')[1]) > 10:
            masked_key = content.split('"')[1][:8] + "..."
            print(f"✅ API密钥格式看起来正确: {masked_key}")
        else:
            print("❌ API密钥格式可能不正确！")
            print("   - 应该包含 'sk-' 前缀")
            print("   - 应该是比较长的字符串")
    else:
        print("❌ 在.env文件中找不到API_DASHSCOPE_API_KEY配置")

if __name__ == "__main__":
    print("🔍 快速检查API密钥配置...")
    check_env_file()
    print("\n📝 下一步:")
    print("1. 如果密钥格式正确，请确保:")
    print("   - 阿里云服务已开通")
    print("   - 账号已完成实名认证")
    print("   - 网络连接正常")
    print("2. 如果密钥格式不正确，请:")
    print("   - 手动编辑.env文件")
    print("   - 替换API密钥为真实的密钥")