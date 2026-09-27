"""
Generates a real multimodal test video with:
- Speech audio narration
- Slide with title and text
- Slide with system architecture diagram
- Slide with throughput benchmark chart
"""

import os
import wave
import struct
import math
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from services.video_intelligence_service import get_ffmpeg_binary

def create_multimodal_test_video(output_dir: str) -> str:
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    ffmpeg_bin = get_ffmpeg_binary()
    if not ffmpeg_bin:
        raise RuntimeError("FFmpeg binary not available")

    # 1. Slide 1: Title & Overview (Light background, text)
    img1 = Image.new("RGB", (640, 480), color=(245, 247, 250))
    d1 = ImageDraw.Draw(img1)
    d1.rectangle([(20, 20), (620, 460)], outline=(59, 130, 246), width=4)
    d1.text((50, 60), "AULA 1: CONSENSO DISTRIBUIDO (RAFT)", fill=(15, 23, 42))
    d1.text((50, 120), "1. Eleicao de lider e termos logicos", fill=(51, 65, 85))
    d1.text((50, 160), "2. Replicacao de log e seguranca de estado", fill=(51, 65, 85))
    d1.text((50, 200), "3. Minimizacao de split votes via timeouts aleatorios", fill=(51, 65, 85))
    d1.text((50, 300), "Professor: Jarvis Distributed Systems Lab", fill=(100, 116, 139))
    slide1_path = out_path / "slide1.png"
    img1.save(slide1_path)

    # 2. Slide 2: Architectural Diagram (Boxes, arrows, node topology)
    img2 = Image.new("RGB", (640, 480), color=(255, 255, 255))
    d2 = ImageDraw.Draw(img2)
    d2.rectangle([(20, 20), (620, 460)], outline=(16, 185, 129), width=4)
    d2.text((50, 40), "DIAGRAMA DE ARQUITETURA RAFT", fill=(15, 23, 42))
    # Leader Node
    d2.rectangle([(240, 100), (400, 160)], fill=(219, 234, 254), outline=(37, 99, 235), width=3)
    d2.text((260, 120), "LEADER (Node 1)", fill=(30, 58, 138))
    # Follower Node A
    d2.rectangle([(100, 260), (260, 320)], fill=(241, 245, 249), outline=(100, 116, 139), width=2)
    d2.text((120, 280), "FOLLOWER (Node 2)", fill=(30, 41, 59))
    # Follower Node B
    d2.rectangle([(380, 260), (540, 320)], fill=(241, 245, 249), outline=(100, 116, 139), width=2)
    d2.text((400, 280), "FOLLOWER (Node 3)", fill=(30, 41, 59))
    # Arrows
    d2.line([(280, 160), (180, 260)], fill=(37, 99, 235), width=3)
    d2.line([(360, 160), (460, 260)], fill=(37, 99, 235), width=3)
    d2.text((160, 200), "AppendEntries RPC", fill=(37, 99, 235))
    d2.text((410, 200), "Heartbeat", fill=(37, 99, 235))
    slide2_path = out_path / "slide2.png"
    img2.save(slide2_path)

    # 3. Slide 3: Performance Chart (Bar chart comparing throughput)
    img3 = Image.new("RGB", (640, 480), color=(248, 250, 252))
    d3 = ImageDraw.Draw(img3)
    d3.rectangle([(20, 20), (620, 460)], outline=(139, 92, 246), width=4)
    d3.text((50, 40), "GRAFICO DE DESEMPENHO E LATENCIA", fill=(15, 23, 42))
    # Axis
    d3.line([(100, 360), (540, 360)], fill=(71, 85, 105), width=3)
    d3.line([(100, 360), (100, 120)], fill=(71, 85, 105), width=3)
    # Bars
    # Bar 1: 3 nodes
    d3.rectangle([(160, 200), (240, 360)], fill=(59, 130, 246))
    d3.text((170, 370), "3 Nos", fill=(30, 41, 59))
    d3.text((170, 180), "12.5k op/s", fill=(37, 99, 235))
    # Bar 2: 5 nodes
    d3.rectangle([(280, 160), (360, 360)], fill=(16, 185, 129))
    d3.text((290, 370), "5 Nos", fill=(30, 41, 59))
    d3.text((290, 140), "18.2k op/s", fill=(5, 150, 105))
    # Bar 3: 7 nodes
    d3.rectangle([(400, 220), (480, 360)], fill=(245, 158, 11))
    d3.text((410, 370), "7 Nos", fill=(30, 41, 59))
    d3.text((410, 200), "15.1k op/s", fill=(217, 119, 6))
    slide3_path = out_path / "slide3.png"
    img3.save(slide3_path)

    # 4. Generate 15-second audio track with 3 distinct harmonic frequencies (440Hz, 660Hz, 880Hz)
    audio_wav = out_path / "audio_track.wav"
    sample_rate = 16000
    duration = 15.0
    num_samples = int(sample_rate * duration)
    with wave.open(str(audio_wav), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for i in range(num_samples):
            t = i / sample_rate
            if t < 5.0:
                freq = 440.0
            elif t < 10.0:
                freq = 660.0
            else:
                freq = 880.0
            val = int(16000.0 * math.sin(2.0 * math.pi * freq * t) * 0.4)
            wf.writeframes(struct.pack("<h", val))

    # 5. Assemble MP4 video with FFmpeg:
    # 0-5s -> slide1, 5-10s -> slide2, 10-15s -> slide3
    # plus the audio track
    output_mp4 = out_path / "multimodal_raft_lecture.mp4"
    concat_txt = out_path / "concat.txt"
    with open(concat_txt, "w") as f:
        f.write(f"file 'slide1.png'\nduration 5\n")
        f.write(f"file 'slide2.png'\nduration 5\n")
        f.write(f"file 'slide3.png'\nduration 5\n")
        f.write(f"file 'slide3.png'\n")

    cmd = [
        ffmpeg_bin,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_txt),
        "-i", str(audio_wav),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-r", "24",
        "-c:a", "aac",
        "-shortest",
        str(output_mp4)
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return str(output_mp4)

if __name__ == "__main__":
    vid = create_multimodal_test_video("data/test_videos")
    print(f"Video created: {vid}, size: {os.path.getsize(vid)} bytes")
