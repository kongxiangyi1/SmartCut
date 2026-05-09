"""
产品介绍模块化功能测试
"""
import sys
import os
from pathlib import Path

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.utils import (
    ProductDetector,
    SegmentClassifier,
    ReuseValueCalculator,
    ReuseLibrary,
    ProductModularTool
)

def test_product_detector():
    """测试产品识别器"""
    print("=== 测试产品识别器 ===")
    detector = ProductDetector()
    
    test_cases = [
        "两千箱光瓶白酒清仓！原价199元，现价99元",
        "这款智能手表具有心率监测功能，游泳级防水",
        "牛肉丸Q弹爽口，火锅必备食材",
        "今天天气真好，我们去散步吧"
    ]
    
    for text in test_cases:
        result = detector.detect_product_features(text)
        print(f"文本: {text[:30]}...")
        print(f"  产品名: {result.get('product_name')}")
        print(f"  类别: {result.get('category')}")
        print(f"  价格: {result.get('price')}")
        print(f"  特征: {result.get('features')}")
        print(f"  促销: {result.get('promotion')}")
        print(f"  置信度: {result.get('confidence')}")
        print()

def test_segment_classifier():
    """测试片段分类器"""
    print("\n=== 测试片段分类器 ===")
    classifier = SegmentClassifier()
    
    sentences = [
        {"text": "你知道为什么这款手表这么受欢迎吗？", "start": 0, "end": 3},
        {"text": "因为它具有心率监测功能", "start": 3, "end": 6},
        {"text": "智能手表原价1999元，现价1299元", "start": 6, "end": 9},
        {"text": "我们品牌始终坚持品质至上的理念", "start": 9, "end": 12},
        {"text": "这款手表真的很不错", "start": 12, "end": 15}
    ]
    
    for i, sentence in enumerate(sentences):
        segment_type = classifier.classify(sentences, i)
        print(f"句子{i+1}: {sentence['text']}")
        print(f"  类型: {segment_type}")
        print()

def test_reuse_value_calculator():
    """测试复用价值计算器"""
    print("\n=== 测试复用价值计算器 ===")
    calculator = ReuseValueCalculator()
    
    test_features = [
        {"product_name": "智能手表", "price": "1999元", "features": ["心率监测", "防水"], "promotion": True},
        {"product_name": "白酒", "price": None, "features": [], "promotion": False},
        {"product_name": None, "price": None, "features": [], "promotion": False}
    ]
    
    for i, features in enumerate(test_features):
        value = calculator.calculate(features)
        breakdown = calculator.get_score_breakdown(features)
        print(f"特征集{i+1}:")
        print(f"  复用价值: {value}")
        print(f"  是否高复用: {calculator.is_high_reuse(features)}")
        print(f"  评分明细: {breakdown}")
        print()

def test_reuse_library():
    """测试复用库管理器"""
    print("\n=== 测试复用库管理器 ===")
    library = ReuseLibrary()
    
    # 添加测试片段
    metadata = {
        "duration": 45.0,
        "product_name": "智能手表",
        "category": "digital",
        "reuse_value": 0.85,
        "tags": ["high_reuse", "digital"],
        "source_clip_id": "test_clip_001",
        "source_video": "test.mp4",
        "source_start": 45.0,
        "source_end": 90.0
    }
    
    clip_path = library.clips_dir / "test_clip.mp4"
    clip_id = library.add_clip(clip_path, metadata)
    print(f"添加片段ID: {clip_id}")
    
    # 搜索测试
    results = library.search_by_product("智能手表")
    print(f"按产品搜索结果: {len(results)} 个")
    
    # 获取统计
    stats = library.get_statistics()
    print(f"统计信息: {stats}")
    
    # 删除测试片段
    deleted = library.delete_clip(clip_id)
    print(f"删除结果: {deleted}")

def test_product_modular_tool():
    """测试产品模块化工具"""
    print("\n=== 测试产品模块化工具 ===")
    tool = ProductModularTool()
    
    test_clip = {
        "id": "test_clip_001",
        "source_video": "test.mp4",
        "sentences": [
            {"text": "你知道为什么这款手表这么受欢迎吗？", "start": 0, "end": 3},
            {"text": "因为它具有心率监测功能", "start": 3, "end": 6},
            {"text": "智能手表原价1999元，现价1299元", "start": 6, "end": 9},
            {"text": "游泳级防水，非常适合运动", "start": 9, "end": 12},
            {"text": "赶紧抢购吧！", "start": 12, "end": 15}
        ]
    }
    
    enhanced_clip = tool._process_clip(test_clip)
    print(f"处理后的切片:")
    print(f"  主类型: {enhanced_clip.get('segment_type')}")
    print(f"  复用价值: {enhanced_clip.get('reuse_value')}")
    print(f"  片段数量: {len(enhanced_clip.get('segments', []))}")
    print(f"  可复用片段: {len(enhanced_clip.get('reusable_clips', []))}")
    
    for i, seg in enumerate(enhanced_clip.get('segments', [])):
        print(f"  片段{i+1}: {seg['type']} [{seg['start']}s-{seg['end']}s], 复用价值: {seg['reuse_value']}")

if __name__ == "__main__":
    print("="*60)
    print("产品介绍模块化功能测试")
    print("="*60)
    
    test_product_detector()
    test_segment_classifier()
    test_reuse_value_calculator()
    # test_reuse_library()  # 暂时跳过
    test_product_modular_tool()
    
    print("\n" + "="*60)
    print("测试完成！")
    print("="*60)