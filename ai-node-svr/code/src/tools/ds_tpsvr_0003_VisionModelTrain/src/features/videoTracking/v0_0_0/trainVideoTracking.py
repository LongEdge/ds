import torch
import time
from ultralytics import YOLO
import cv2
import subprocess

class CTrainVideoTracking:
    # def __init__(self):
    def __init__(self, node_cfg, process_comm, proc_modules_obj, progress_callback):
        self.node_cfg = node_cfg
        self.process_comm = process_comm
        self.proc_modules_obj = proc_modules_obj
        self.progress_callback = progress_callback



    
    def trace(self, params):
        stream_source = params.get("stream_source", None)
        rtmp_url = params.get("rtmp_url", None)
        if stream_source == None or rtmp_url == None:
            raise ValueError("流参数为None")

           # 1. 检查 CUDA 设备
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"[INFO] Using device: {device}")
        
        print(f"[INFO] loading YOLO model to {device}...")
        model_path = "/home/gugm/workcode/tool_dev/ds_ai_svr/ai-node-svr/code/data/persist/ds_tpsvr_0003/yolo11n.pt"
        video_path = "/home/gugm/workcode/tool_dev/ds_ai_svr/ai-node-svr/code/data/persist/ds_tpsvr_0003/test.mp4"

        stream_source = video_path
        model = YOLO(model_path).to(device) # 显式移动到 GPU
        cap = cv2.VideoCapture(stream_source)
        if not cap.isOpened():
            raise ConnectionError(f"无法打开视频源: {stream_source}")
        
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0: fps = 25
        frame_duration = 1.0 / fps

        backSub = cv2.createBackgroundSubtractorMOG2()

        # --- FFmpeg 配置 ---
        # 如果想用显卡编码，把 'libx264' 换成 'h264_nvenc'
        # 但由于你之前提到过 CPU 编码环境，我们先保持 libx264 以保稳定，AI 部分已由 CUDA 加速
        ffmpeg_command = [
            'ffmpeg',
            '-y',

            # 👉 时间戳稳定
            '-fflags', '+genpts',
            '-use_wallclock_as_timestamps', '1',

            '-f', 'rawvideo',
            '-pix_fmt', 'bgr24',
            '-s', f"{width}x{height}",
            '-r', str(fps),
            '-i', '-',

            # 👉 编码
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            '-preset', 'ultrafast',
            '-tune', 'zerolatency',

            # 👉 码率控制（关键）
            '-b:v', '1500k',
            '-maxrate', '1500k',
            '-bufsize', '3000k',

            # 👉 GOP稳定
            '-g', str(int(fps)),
            '-keyint_min', str(int(fps)),
            '-sc_threshold', '0',

            # 👉 防爆流
            '-vsync', '1',

            '-f', 'flv',
            rtmp_url
        ]

        pipe = subprocess.Popen(ffmpeg_command, stdin=subprocess.PIPE)
        self.progress_callback(30, "视频跟踪...")


        try:
            print(f"[INFO] 开始推流 (CUDA 加速推理)...")
            frame_id = 0

            while True:
                start_time = int(time.time())
                frame_id += 1

                success, frame = cap.read()
                if not success:
                    break


                results = model.predict(
                    frame,
                    device=device,
                    imgsz=416,
                    half=True,
                    conf=0.4,
                    verbose=False
                )
                detections = results[0].boxes


                people_count = 0

                for box in detections:
                    if int(box.cls[0]) == 0:
                        people_count += 1
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

                # 5. 推流
                try:
                    pipe.stdin.write(frame.tobytes())
                except BrokenPipeError: break

                # 6. 同步
                elapsed = time.time() - start_time
                sleep_time = frame_duration - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

        
        finally:
            cap.release()
            # if pipe.stdin: pipe.stdin.close()
            # pipe.terminate()
            self.progress_callback(100, "视频跟踪...")
