
import json
data = json.load(open(r'e:\ClipProject\autoclip-main1\autoclip-main\data\projects.json', 'r', encoding='utf-8'))
project_id = '7142000a-957a-4dcf-89e6-7c8a124bb8c3'
for p in data:
    if p['id'] == project_id:
        print(f"项目: {p['name']} ({p['status']})")
        print(f"切片数: {len(p.get('clips', []))}")
        print(f"合集数: {len(p.get('collections', []))}")
        if 'error_message' in p:
            print(f"错误消息: {p['error_message']}")
        
        print("\n前5个切片:")
        for i, clip in enumerate(p.get('clips', [])[:5]):
            print(f"  {i+1}. {clip.get('generated_title', '无标题')} - {clip.get('start_time')} 到 {clip.get('end_time')}")
        break
