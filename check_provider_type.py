"""
检查后端服务器使用的 ProviderType 定义
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# 检查 llm_providers.py 文件的内容
from backend.core import llm_providers

# 打印枚举定义
print("ProviderType 枚举定义:")
print(f"文件路径: {llm_providers.__file__}")
print("-" * 50)
print("枚举成员:")
for member in llm_providers.ProviderType:
    print(f"  - {member.name} = '{member.value}'")

# 测试转换
print("\n测试字符串转换:")
test_value = "tencent"
try:
    pt = llm_providers.ProviderType(test_value)
    print(f"✅ '{test_value}' -> {pt}")
except ValueError as e:
    print(f"❌ '{test_value}' -> {e}")

# 打印文件内容
print("\n检查文件内容:")
with open(llm_providers.__file__, 'r', encoding='utf-8') as f:
    content = f.read()
    # 查找 ProviderType 定义
    start = content.find("class ProviderType")
    end = content.find("@dataclass", start)
    print(content[start:end])