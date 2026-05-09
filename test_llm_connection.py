"""
测试LLM连接是否正常工作
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from core.llm_manager import get_llm_manager

def test_llm_connection():
    print("正在测试LLM连接...")
    
    try:
        llm_manager = get_llm_manager()
        provider_info = llm_manager.get_current_provider_info()
        print(f"当前提供商: {provider_info}")
        
        if not llm_manager.current_provider:
            print("❌ 提供商未初始化")
            return False
            
        # 测试API调用
        print("正在调用LLM...")
        response = llm_manager.call("请用中文回复一个简单的测试消息")
        print(f"响应内容: {response[:50]}...")
        print("✅ LLM连接测试成功")
        return True
        
    except Exception as e:
        print(f"❌ LLM连接测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_llm_connection()
    sys.exit(0 if success else 1)