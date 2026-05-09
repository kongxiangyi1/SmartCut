import sys
from pathlib import Path
import json

sys.path.insert(0, 'e:\\ClipProject\\autoclip-main1\\autoclip-main')

from funasr import AutoModel

audio_path = Path('e:\\ClipProject\\autoclip-main1\\autoclip-main\\data\\projects\\4afb7d15-ec2b-48c3-ad63-46b5129194da\\metadata\\input_audio.wav')

model = AutoModel(
    model='paraformer-zh',
    vad_model='fsmn-vad',
    punc_model='ct-punc',
    device='cpu'
)

result = model.generate(input=str(audio_path))

print(f'Result type: {type(result)}')
print(f'Result length: {len(result)}')
print(f'First element type: {type(result[0])}')

# 尝试打印详细信息
try:
    print(f'First element repr: {repr(result[0])[:500]}')
except:
    pass

# 尝试访问各种可能的字段
if isinstance(result[0], dict):
    print(f'Keys: {list(result[0].keys())}')
    
    # 尝试获取各种可能的字段
    for key in ['value', 'text', 'start', 'end', 'time_stamp', 'timestamp']:
        if key in result[0]:
            print(f'{key}: {result[0][key]}')
