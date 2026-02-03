import json
import os
import subprocess
import urllib.request
import shutil
import textwrap
import sys
import re
import base64


# --- 설정 ---
FONT_PATH = '/usr/share/fonts/truetype/nanum/NanumGothic.ttf'
VIDEO_WIDTH = 1280
VIDEO_HEIGHT = 720
# -------------

def run_command(command):
    """주어진 명령어를 실행하고 결과를 출력합니다."""
    try:
        print(f"Executing: {' '.join(command)}")
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {' '.join(command)}")
        print(f"Stderr: {e.stderr}")
        raise

def download_assets(characters, temp_dir):
    """캐릭터 이미지를 다운로드하고 로컬 경로를 반환합니다."""
    image_paths = {}
    for char in characters:
        name = char['name']
        url = char['image_url']
        extension = os.path.splitext(url)[1].split('?')[0] or '.png'
        image_path = os.path.join(temp_dir, f"{name}{extension}")
        print(f"Downloading {name}'s image from {url} to {image_path}")
        urllib.request.urlretrieve(url, image_path)
        image_paths[name] = image_path
    return image_paths

def create_video_clip(clip_path, dialogue_item, characters, image_paths, temp_dir, clip_index):
    """한 줄의 대사를 위한 음성 포함 비디오 클립을 생성합니다."""
    speaker_name = dialogue_item['speaker']
    line = dialogue_item['line']
    bg_image_url = dialogue_item.get('bg_image_url')
    
    # --- TTS로 음성 파일 생성 ---
    audio_path = os.path.join(temp_dir, f"line_{clip_index}.wav")
    safe_text = line.replace("'", "").replace("`", "").replace('"', '')
    tts_command = ['espeak-ng', '-v', 'ko', '-w', audio_path, safe_text]
    run_command(tts_command)

    # --- FFprobe로 음성 파일 길이 측정 ---
    ffprobe_command = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', audio_path]
    duration_str = subprocess.check_output(ffprobe_command).decode('utf-8').strip()
    duration = float(duration_str) + 0.5  # 0.5초 여유 추가

    # --- FFmpeg 입력 및 필터그래프 구성 ---
    inputs = []
    filter_complex_elements = []
    
    # 입력 0: 배경
    background_stream_name = "[0:v]"
    if bg_image_url and (bg_image_url.startswith('http') or bg_image_url.startswith('data:image')):
        try:
            if bg_image_url.startswith('data:image'):
                bg_image_path = os.path.join(temp_dir, f"background_{clip_index}.png")
                img_data = base64.b64decode(bg_image_url.split(',')[1])
                with open(bg_image_path, 'wb') as f: f.write(img_data)
            else:
                bg_image_path = os.path.join(temp_dir, f"background_{clip_index}{os.path.splitext(urllib.parse.urlparse(bg_image_url).path)[1] or '.jpg'}")
                urllib.request.urlretrieve(bg_image_url, bg_image_path)
            
            inputs.extend(['-loop', '1', '-i', bg_image_path])
            filter_complex_elements.append(f"[0:v]scale={VIDEO_WIDTH}:{VIDEO_HEIGHT},setsar=1[bg]")
            background_stream_name = "[bg]"
        except Exception as e:
            print(f"Failed to use background image: {e}. Using white background.")
            inputs.extend(['-f', 'lavfi', '-i', f'color=c=white:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:d={duration}'])
    else:
        inputs.extend(['-f', 'lavfi', '-i', f'color=c=white:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:d={duration}'])

    # 입력 1: 오디오
    inputs.extend(['-i', audio_path])

    # 입력 2 & 3: 캐릭터 이미지
    inputs.extend(['-i', image_paths[characters[0]['name']]]) # Alex
    inputs.extend(['-i', image_paths[characters[1]['name']]]) # Ben

    # 캐릭터 이미지 스케일 및 투명도 조절
    filter_complex_elements.extend([
        "[2:v]scale=300:300[scaled_alex]",
        "[3:v]scale=300:300[scaled_ben]"
    ])
    
    if speaker_name == characters[0]['name']: # Alex
        filter_complex_elements.extend([
            "[scaled_alex]format=rgba[img_alex]",
            "[scaled_ben]format=rgba,colorchannelmixer=aa=0.5[img_ben]"
        ])
    else: # Ben
        filter_complex_elements.extend([
            "[scaled_alex]format=rgba,colorchannelmixer=aa=0.5[img_alex]",
            "[scaled_ben]format=rgba[img_ben]"
        ])

    # 오버레이 및 텍스트 추가
    filter_complex_elements.extend([
        f"{background_stream_name}[img_alex]overlay=140:210[bg1]",
        f"[bg1][img_ben]overlay=840:210[final_bg_chars]"
    ])
    
    wrapped_text = textwrap.fill(line, width=40)
    escaped_text = wrapped_text.replace("'", "'\\''")
    filter_complex_elements.append(f"[final_bg_chars]drawtext=text='{speaker_name}: {escaped_text}':fontfile={FONT_PATH}:fontsize=32:fontcolor=black:x=(w-text_w)/2:y={VIDEO_HEIGHT - 100}[outv]")

    # --- FFmpeg 명령어 생성 및 실행 ---
    command = [
        'ffmpeg', '-y', *inputs,
        '-filter_complex', ";".join(filter_complex_elements),
        '-map', '[outv]',
        '-map', '1:a', # 오디오는 항상 입력 1번
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac',
        '-shortest',
        clip_path
    ]
    run_command(command)



def main(script_filepath):
    """메인 실행 함수"""
    
    # 1. JSON 파일 읽기
    try:
        with open(script_filepath, 'r', encoding='utf-8') as f:
            script_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Script file not found at {script_filepath}")
        return
    except json.JSONDecodeError:
        print(f"Error: {script_filepath} is not a valid JSON file.")
        return

    title = script_data.get('title', 'video')
    safe_title = re.sub(r'[\\/*?:"<>|]', '_', title)
    output_filename = f"{safe_title}.mp4"
    
    temp_dir = 'temp_video_assets'
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)

    print(f"--- Starting Video Generation for '{title}' ---")

    try:
        # 3. 캐릭터 에셋 다운로드
        print("\n--- Downloading Assets ---")
        image_paths = download_assets(script_data['characters'], temp_dir)

        # 4. 클립 생성
        print("\n--- Generating Video Clips ---")
        clip_files = []
        for i, dialogue_item in enumerate(script_data['dialogue']):
            clip_path = os.path.join(temp_dir, f"line_{i+1}.mp4")
            # duration 계산 제거, create_video_clip이 음성 길이에 따라 결정
            create_video_clip(clip_path, dialogue_item, script_data['characters'], image_paths, temp_dir, i + 1)
            clip_files.append(clip_path)

        # 5. 클립 합치기
        print("\n--- Concatenating Clips ---")
        file_list_path = os.path.join(temp_dir, 'file_list.txt')
        with open(file_list_path, 'w') as f:
            for clip_file in clip_files:
                f.write(f"file '{os.path.basename(clip_file)}'\n")
        
        concat_command = [
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'file_list.txt',
            '-c', 'copy', output_filename
        ]
        try:
            subprocess.run(concat_command, check=True, cwd=temp_dir, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            print(f"Error during concatenation: {' '.join(e.cmd)}")
            print(f"ffmpeg stderr:\n{e.stderr}")
            raise
        shutil.move(os.path.join(temp_dir, output_filename), output_filename)

        print(f"\n--- Success! Video saved as {output_filename} ---")

    finally:
        print("\n--- Cleaning up temporary files ---")
        shutil.rmtree(temp_dir)

if __name__ == '__main__':
    # 인자가 없으면 기본 'script.json'을 사용
    if len(sys.argv) > 1:
        script_to_process = sys.argv[1]
    else:
        script_to_process = 'script.json'
    
    main(script_to_process)
