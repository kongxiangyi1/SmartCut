        successful, _ = self.video_processor.batch_extract_clips(video_path, clips_data)
        return [str(p) for p in successful]