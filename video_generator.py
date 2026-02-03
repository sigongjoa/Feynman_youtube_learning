import json
import os
import subprocess
import urllib.request
import shutil
import textwrap

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

def create_video_clip(clip_path, dialogue_item, characters, image_paths, duration=5):
    """한 줄의 대사를 위한 비디오 클립을 생성합니다."""
    speaker_name = dialogue_item['speaker']
    line = dialogue_item['line']
    
    # 텍스트 줄바꿈 처리
    wrapped_text = textwrap.fill(line, width=40)

    # FFmpeg 필터그래프 구성
    filter_complex = []
    
    # 입력 설정 (배경, 이미지들)
    inputs = ['-f', 'lavfi', '-i', f'color=c=white:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:d={duration}']
    
    # 캐릭터 이미지 스케일 및 투명도 조절
    speaker_img_idx = -1
    for i, char in enumerate(characters):
        char_name = char['name']
        char_path = image_paths[char_name]
        inputs.extend(['-i', char_path])
        
        stream_idx = i + 1
        overlay_name = f"char{stream_idx}"
        
        filter_complex.append(f"[{stream_idx}:v]scale=300:300[scaled{stream_idx}]")
        
        if char_name == speaker_name:
            speaker_img_idx = stream_idx
            filter_complex.append(f"[scaled{stream_idx}]format=rgba[img{stream_idx}]")
        else:
            filter_complex.append(f"[scaled{stream_idx}]format=rgba,colorchannelmixer=aa=0.5[img{stream_idx}]")

    # 오버레이 필터 구성 (수정된 부분)
    # 캐릭터들을 정해진 위치(Alex 왼쪽, Ben 오른쪽)에 오버레이합니다.
    filter_complex.append("[0:v][img1]overlay=140:210[bg1]")
    filter_complex.append("[bg1][img2]overlay=840:210[final_bg]")

    # 텍스트 오버레이 추가
    filter_complex.append(f"[final_bg]drawtext=text='{speaker_name}: {wrapped_text}':fontfile={FONT_PATH}:fontsize=32:fontcolor=black:x=(w-text_w)/2:y={VIDEO_HEIGHT - 100}")

    # FFmpeg 명령어 생성
    command = [
        'ffmpeg', '-y', *inputs,
        '-filter_complex', ";".join(filter_complex),
        '-c:v', 'libx264',
        '-pix_fmt', 'yuv420p',
        clip_path
    ]
    run_command(command)


def main():
    """메인 실행 함수"""
    
    # 1. JSON 파일 읽기
    try:
        with open('script.json', 'r', encoding='utf-8') as f:
            script_data = json.load(f)
    except FileNotFoundError:
        print("Error: script.json not found. Please create it first.")
        return
    except json.JSONDecodeError:
        print("Error: script.json is not a valid JSON file.")
        return

    title = script_data.get('title', 'video')
    output_filename = f"{title.replace(' ', '_')}.mp4"
    
    # 2. 임시 디렉토리 생성
    temp_dir = 'temp_video_assets'
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)

    print(f"--- Starting Video Generation for '{title}' ---")

    try:
        # 3. 에셋 다운로드
        print("\n--- Downloading Assets ---")
        image_paths = download_assets(script_data['characters'], temp_dir)

        # 4. 클립 생성
        print("\n--- Generating Video Clips ---")
        clip_files = []
        for i, dialogue_item in enumerate(script_data['dialogue']):
            clip_path = os.path.join(temp_dir, f"line_{i+1}.mp4")
            duration = max(5, int(len(dialogue_item['line']) / 10)) # 대사 길이에 따라 시간 조절
            create_video_clip(clip_path, dialogue_item, script_data['characters'], image_paths, duration)
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
        # Concat 명령어는 temp_dir 안에서 실행해야 경로 문제가 없음
        subprocess.run(concat_command, check=True, cwd=temp_dir, capture_output=True, text=True)
        # 최종 파일을 현재 디렉토리로 이동
        shutil.move(os.path.join(temp_dir, output_filename), output_filename)


        print(f"\n--- Success! Video saved as {output_filename} ---")

    finally:
        # 6. 임시 파일 정리
        print("\n--- Cleaning up temporary files ---")
        shutil.rmtree(temp_dir)

if __name__ == '__main__':
    main()
