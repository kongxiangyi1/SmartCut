"""
测试 API 接口中的 ProviderType 枚举转换
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

def test_provider_type_conversion():
    print("测试 ProviderType 枚举转换...")
    
    from backend.core.llm_providers import ProviderType
    
    # 测试从字符串转换
    providers = ["dashscope", "openai", "gemini", "siliconflow", "zhipu", "tencent"]
    
    for provider in providers:
        try:
            provider_type = ProviderType(provider)
            print(f"✅ '{provider}' -> {provider_type}")
        except ValueError as e:
            print(f"❌ '{provider}' -> {e}")
    
    # 测试 tencent 特别
    print("\n特别测试 tencent:")
    try:
        provider_type = ProviderType("tencent")
        print(f"✅ tencent 转换成功: {provider_type}, value={provider_type.value}")
    except ValueError as e:
        print(f"❌ tencent 转换失败: {e}")
    
    # 测试无效值
    print("\n测试无效值:")
    try:
        provider_type = ProviderType("invalid_provider")
        print(f"❌ 不应该成功: {provider_type}")
    except ValueError as e:
        print(f"✅ 无效值正确抛出异常: {e}")

if __name__ == "__main__":
    test_provider_type_conversion()