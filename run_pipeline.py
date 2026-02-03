import subprocess
import os
import glob
import sys

def run_step(command: list, step_name: str):
    """
    파이프라인의 한 단계를 실행하고 성공 여부를 확인합니다.
    """
    print(f"--- Running Step: {step_name} ---")
    print(f"Executing: {' '.join(command)}\n")
    try:
        subprocess.run(command, check=True, text=True) # capture_output=True를 제거하여 실시간 출력 확인
        print(f"--- Step Succeeded: {step_name} ---\n")
        return True
    except subprocess.CalledProcessError as e:
        print(f"!!! Step Failed: {step_name} !!!")
        print(f"Return code: {e.returncode}")
        if e.stdout:
            print(f"Stdout: {e.stdout}")
        if e.stderr:
            print(f"Stderr: {e.stderr}")
        return False
    except FileNotFoundError:
        print(f"!!! Command not found: {command[0]}. Make sure Python is installed and in your PATH.")
        return False

def main():
    """
    전체 영상 제작 파이프라인을 실행하는 오케스트레이터 함수
    """
    print("=============================================")
    print("=== Starting Automated Video Generation Pipeline ===")
    print("=============================================\n")

    # --- 1단계: 논문 크롤링 ---
    if not run_step(['python3', 'crawler.py'], "Crawl latest papers"):
        sys.exit(1) # 크롤링 실패 시 중단

    # --- 2단계: 수집된 각 논문에 대해 영상 제작 ---
    crawled_papers_dir = "crawled_papers"
    paper_files = glob.glob(os.path.join(crawled_papers_dir, '*.txt'))
    
    if not paper_files:
        print("No papers found to process. Exiting.")
        return

    print(f"Found {len(paper_files)} papers to process.\n")
    
    successful_videos = []
    failed_papers = []

    for paper_file in paper_files:
        print(f"--- Processing paper: {paper_file} ---")
        
        # 2a: 콘텐츠 처리 (텍스트 -> 대본)
        if not run_step(['python3', 'content_processor.py', paper_file], f"Process content for {paper_file}"):
            failed_papers.append(paper_file)
            continue
            
        # 생성된 스크립트 파일 이름 추정
        base_filename = os.path.basename(paper_file)
        name_without_ext = os.path.splitext(base_filename)[0]
        script_file = f"script_{name_without_ext}.json"
        
        if not os.path.exists(script_file):
            print(f"!!! Error: Expected script file {script_file} was not created. Skipping video generation.")
            failed_papers.append(paper_file)
            continue
            
        video_generation_successful = run_step(['python3', 'video_generator.py', script_file], f"Generate video for {script_file}")
        if not video_generation_successful:
            failed_papers.append(paper_file)
            # 영상 생성 실패 시에도 paper_file은 삭제, script_file은 보존 (디버깅용)
            os.remove(paper_file)
            print(f"Kept {script_file} for debugging purposes due to video generation failure.")
            continue
        else:
            # 생성된 비디오 파일 이름 추정
            # video_generator.py의 로직과 일치해야 함
            with open(script_file, 'r', encoding='utf-8') as f:
                title = json.load(f).get('title', '')
            safe_title = re.sub(r'[\\/*?:\"<>|]', '_', title)
            video_filename = f"{safe_title}.mp4"

            successful_videos.append(video_filename)
            
            # 2c: 중간 파일 정리 (성공 시에만)
            print(f"--- Cleaning up intermediate files for {paper_file} ---")
            os.remove(paper_file)
            os.remove(script_file)
            print("Cleanup complete.\n")

    # --- 최종 요약 ---
    print("\n=============================================")
    print("=== Pipeline Finished ===")
    print("=============================================")
    if successful_videos:
        print("Successfully generated videos:")
        for video in successful_videos:
            print(f"- {video}")
    if failed_papers:
        print("\nFailed to process papers:")
        for paper in failed_papers:
            print(f"- {paper}")

if __name__ == '__main__':
    # content_processor.py에서 필요했던 json과 re 모듈을 여기서도 임포트
    import json
    import re
    main()
