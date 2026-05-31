try:
    from .environment_detector import EnvironmentDetector
except Exception:
    EnvironmentDetector = None

try:
    from .video_processor import VideoProcessor
except Exception:
    VideoProcessor = None

try:
    from .logging_config import setup_logging
except Exception:
    setup_logging = None

try:
    from .vad_preprocessor import VADPreprocessor, get_vad_preprocessor
except Exception:
    VADPreprocessor = None
    get_vad_preprocessor = None

__all__ = [
    'EnvironmentDetector',
    'VideoProcessor',
    'setup_logging',
    'VADPreprocessor',
    'get_vad_preprocessor'
]
