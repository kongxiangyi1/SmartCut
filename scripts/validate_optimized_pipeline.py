#!/usr/bin/env python3
"""
AutoClip 流水线优化验证脚本
用于验证优化后的流水线是否正常工作
"""

import sys
import json
import logging
from pathlib import Path

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_imports():
    """测试1: 验证所有模块可以正常导入"""
    logger.info("测试1: 验证模块导入...")
    
    try:
        # 测试优化模块导入
        from backend.pipeline.optimized import (
            IntelligentAnalyzer,
            SmartClusterer,
            OptimizedPipeline,
            run_optimized_pipeline
        )
        logger.info("  ✅ 优化模块导入成功")
        
        # 测试流水线选择器导入
        from backend.pipeline.pipeline_selector import PipelineSelector
        logger.info("  ✅ 流水线选择器导入成功")
        
        return True
    except ImportError as e:
        logger.error(f"  ❌ 导入失败: {e}")
        return False


def test_config():
    """测试2: 验证配置"""
    logger.info("测试2: 验证配置...")
    
    try:
        from backend.pipeline.optimized.config import (
            OPTIMIZED_PIPELINE_ENABLED,
            CLUSTERING_MODE,
            CLUSTER_MIN_CLIPS,
            MAX_CLIPS_PER_COLLECTION
        )
        
        logger.info(f"  优化流水线启用: {OPTIMIZED_PIPELINE_ENABLED}")
        logger.info(f"  聚类模式: {CLUSTERING_MODE}")
        logger.info(f"  最少切片数: {CLUSTER_MIN_CLIPS}")
        logger.info(f"  每合集最多切片: {MAX_CLIPS_PER_COLLECTION}")
        logger.info("  ✅ 配置加载成功")
        
        return True
    except Exception as e:
        logger.error(f"  ❌ 配置加载失败: {e}")
        return False


def test_analyzer_creation():
    """测试3: 验证分析器可以创建"""
    logger.info("测试3: 验证分析器创建...")
    
    try:
        from backend.pipeline.optimized import IntelligentAnalyzer
        
        analyzer = IntelligentAnalyzer()
        logger.info(f"  ✅ 分析器创建成功: {type(analyzer).__name__}")
        
        return True
    except Exception as e:
        logger.error(f"  ❌ 分析器创建失败: {e}")
        return False


def test_clusterer_creation():
    """测试4: 验证聚类器可以创建"""
    logger.info("测试4: 验证聚类器创建...")
    
    try:
        from backend.pipeline.optimized import SmartClusterer
        
        clusterer = SmartClusterer()
        logger.info(f"  ✅ 聚类器创建成功: {type(clusterer).__name__}")
        
        return True
    except Exception as e:
        logger.error(f"  ❌ 聚类器创建失败: {e}")
        return False


def test_clustering_logic():
    """测试5: 验证聚类逻辑"""
    logger.info("测试5: 验证聚类逻辑...")
    
    try:
        from backend.pipeline.optimized import SmartClusterer
        
        clusterer = SmartClusterer()
        
        # 测试数据
        test_clips = [
            {
                'id': '1',
                'outline': '投资理财技巧',
                'generated_title': '如何科学投资',
                'recommend_reason': '分享实用投资技巧',
                'final_score': 0.85,
                'content': ['股票投资', '基金配置']
            },
            {
                'id': '2',
                'outline': '职场技能提升',
                'generated_title': '提升职场竞争力',
                'recommend_reason': '实用职场建议',
                'final_score': 0.75,
                'content': ['技能学习', '职业发展']
            }
        ]
        
        # 执行聚类
        collections = clusterer.cluster(test_clips, use_llm_refine=False)
        
        logger.info(f"  聚类结果: {len(collections)} 个合集")
        for col in collections:
            logger.info(f"    - {col['collection_title']}: {len(col['clip_ids'])} 个切片")
        
        logger.info("  ✅ 聚类逻辑测试通过")
        
        return True
    except Exception as e:
        logger.error(f"  ❌ 聚类逻辑测试失败: {e}")
        return False


def test_pipeline_selector():
    """测试6: 验证流水线选择器"""
    logger.info("测试6: 验证流水线选择器...")
    
    try:
        from backend.pipeline.pipeline_selector import PipelineSelector
        
        selector = PipelineSelector()
        
        # 测试选择逻辑
        legacy_result = selector.select_pipeline("test-project-1")
        optimized_result = selector.select_pipeline("test-project-2")
        
        logger.info(f"  项目1 选择: {legacy_result}")
        logger.info(f"  项目2 选择: {optimized_result}")
        logger.info("  ✅ 流水线选择器测试通过")
        
        return True
    except Exception as e:
        logger.error(f"  ❌ 流水线选择器测试失败: {e}")
        return False


def test_api_registration():
    """测试7: 验证 API 路由注册"""
    logger.info("测试7: 验证 API 路由注册...")
    
    try:
        from backend.api.v1 import api_router
        
        routes = [r.path for r in api_router.routes]
        logger.info(f"  已注册的路由数量: {len(routes)}")
        
        # 检查流水线相关路由
        pipeline_routes = [r for r in routes if 'pipeline' in r]
        logger.info(f"  流水线相关路由: {pipeline_routes}")
        
        if pipeline_routes:
            logger.info("  ✅ API 路由注册成功")
            return True
        else:
            logger.warning("  ⚠️ 未找到流水线相关路由")
            return False
            
    except Exception as e:
        logger.error(f"  ❌ API 路由注册失败: {e}")
        return False


def run_all_tests():
    """运行所有测试"""
    logger.info("=" * 60)
    logger.info("开始 AutoClip 流水线优化验证测试")
    logger.info("=" * 60)
    
    tests = [
        ("模块导入", test_imports),
        ("配置加载", test_config),
        ("分析器创建", test_analyzer_creation),
        ("聚类器创建", test_clusterer_creation),
        ("聚类逻辑", test_clustering_logic),
        ("流水线选择器", test_pipeline_selector),
        ("API路由注册", test_api_registration),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, "✅ PASS" if result else "❌ FAIL", result))
        except Exception as e:
            logger.error(f"测试 '{name}' 异常: {e}")
            results.append((name, "❌ ERROR", False))
        
        logger.info("")
    
    # 输出汇总
    logger.info("=" * 60)
    logger.info("测试结果汇总")
    logger.info("=" * 60)
    
    passed = sum(1 for _, _, r in results if r)
    failed = len(results) - passed
    
    for name, status, _ in results:
        logger.info(f"  {status} - {name}")
    
    logger.info("")
    logger.info(f"总计: {len(results)} 个测试")
    logger.info(f"通过: {passed} 个")
    logger.info(f"失败: {failed} 个")
    
    if failed == 0:
        logger.info("")
        logger.info("🎉 所有测试通过！优化流水线已准备就绪。")
        return True
    else:
        logger.warning("")
        logger.warning("⚠️ 部分测试失败，请检查日志。")
        return False


if __name__ == "__main__":
    # 添加项目根目录到 Python 路径
    project_root = Path(__file__).parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
    success = run_all_tests()
    sys.exit(0 if success else 1)
