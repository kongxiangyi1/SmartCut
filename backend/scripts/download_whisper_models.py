"""
下载并打包 Whisper tiny + base 模型

使用方法:
    python download_whisper_models.py [--models tiny,base] [--output ./models]

此脚本用于离线部署，将 Whisper 模型预先下载到指定目录。
"""

import argparse
import os
import sys
from pathlib import Path


def download_whisper_models(models=None, output_dir=None):
    """
    下载 Whisper 模型到指定目录

    Args:
        models: 要下载的模型列表，如 ['tiny', 'base']
        output_dir: 输出目录路径
    """
    if models is None:
        models = ['tiny', 'base']

    if output_dir is None:
        output_dir = Path(__file__).parent.parent.parent / 'models' / 'whisper'
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"📦 将下载 Whisper 模型到: {output_dir}")
    print(f"📋 模型列表: {', '.join(models)}")
    print()

    try:
        import torch
        import whisper
    except ImportError:
        print("❌ 错误: 请先安装 whisper 和 torch")
        print("   运行: pip install openai-whisper torch")
        sys.exit(1)

    for model_name in models:
        print(f"\n🔽 正在下载模型: {model_name}")

        try:
            model_path = output_dir / f"{model_name}.pt"

            if model_path.exists():
                file_size = model_path.stat().st_size / (1024 * 1024)
                print(f"   ✅ 模型已存在: {model_path} ({file_size:.1f} MB)")
                continue

            print(f"   ⏳ 正在下载 {model_name} 模型 (约 72-139 MB)...")

            model = whisper.load_model(model_name, download_root=str(output_dir))

            actual_path = output_dir / f"{model_name}.pt"
            if actual_path.exists():
                file_size = actual_path.stat().st_size / (1024 * 1024)
                print(f"   ✅ 下载完成: {actual_path} ({file_size:.1f} MB)")
            else:
                for f in output_dir.glob(f"{model_name}*"):
                    if f.suffix == '.pt':
                        file_size = f.stat().st_size / (1024 * 1024)
                        print(f"   ✅ 下载完成: {f} ({file_size:.1f} MB)")
                        break

        except Exception as e:
            print(f"   ❌ 下载失败: {e}")
            continue

    print("\n" + "=" * 50)
    print("📊 下载统计:")
    total_size = sum(f.stat().st_size for f in output_dir.glob("*.pt"))
    print(f"   总大小: {total_size / (1024 * 1024):.1f} MB")
    print(f"   保存位置: {output_dir}")
    print("=" * 50)


def verify_models(models_dir):
    """
    验证已下载的模型

    Args:
        models_dir: 模型目录路径
    """
    models_dir = Path(models_dir)

    if not models_dir.exists():
        print(f"❌ 模型目录不存在: {models_dir}")
        return False

    print(f"\n🔍 验证模型目录: {models_dir}")

    expected_models = {
        'tiny': 72,
        'base': 139,
        'small': 461,
        'medium': 1457,
        'large': 2944
    }

    all_valid = True
    for model_name, expected_size_mb in expected_models.items():
        model_path = models_dir / f"{model_name}.pt"

        if model_path.exists():
            size_mb = model_path.stat().st_size / (1024 * 1024)
            if size_mb > expected_size_mb * 0.8:
                print(f"   ✅ {model_name}: {size_mb:.1f} MB (有效)")
            else:
                print(f"   ⚠️ {model_name}: {size_mb:.1f} MB (文件过小，可能损坏)")
                all_valid = False
        else:
            print(f"   ⭕ {model_name}: 未找到")

    return all_valid


def get_cache_dir():
    """获取 Whisper 默认缓存目录"""
    if os.name == 'nt':
        base = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
        return Path(base) / 'Cache' / 'whisper'
    else:
        return Path.home() / '.cache' / 'whisper'


def copy_models_to_package(models_dir, package_dir):
    """
    将模型复制到打包目录

    Args:
        models_dir: 模型源目录
        package_dir: 打包目标目录
    """
    models_dir = Path(models_dir)
    package_dir = Path(package_dir) / 'whisper_models'
    package_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n📦 复制模型到打包目录: {package_dir}")

    for model_file in models_dir.glob("tiny*.pt"):
        import shutil
        dest = package_dir / model_file.name
        shutil.copy2(model_file, dest)
        print(f"   ✅ 已复制: {model_file.name}")

    for model_file in models_dir.glob("base*.pt"):
        import shutil
        dest = package_dir / model_file.name
        shutil.copy2(model_file, dest)
        print(f"   ✅ 已复制: {model_file.name}")

    print(f"\n📊 打包目录总大小:")
    total = sum(f.stat().st_size for f in package_dir.glob("*.pt"))
    print(f"   {total / (1024 * 1024):.1f} MB")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='下载 Whisper 模型')
    parser.add_argument(
        '--models',
        type=str,
        default='tiny,base',
        help='要下载的模型，用逗号分隔 (默认: tiny,base)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='输出目录 (默认: ./models/whisper)'
    )
    parser.add_argument(
        '--verify',
        action='store_true',
        help='验证已下载的模型'
    )
    parser.add_argument(
        '--copy-to-package',
        type=str,
        default=None,
        help='复制模型到打包目录'
    )

    args = parser.parse_args()

    if args.verify:
        cache_dir = get_cache_dir()
        verify_models(cache_dir)
    elif args.copy_to_package:
        cache_dir = get_cache_dir()
        copy_models_to_package(cache_dir, args.copy_to_package)
    else:
        models = [m.strip() for m in args.models.split(',')]
        download_whisper_models(models=models, output_dir=args.output)
