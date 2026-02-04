import subprocess
import os
import glob
import sys
import json
import re

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
    
    successful_scripts = []
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

        if os.path.exists(script_file):
            successful_scripts.append(script_file)
            print(f"--- Successfully generated script: {script_file} ---")
            # 원본 논문 텍스트 파일은 이제 필요 없으므로 삭제
            os.remove(paper_file)
        else:
            print(f"!!! Error: Expected script file {script_file} was not created.")
            failed_papers.append(paper_file)

    # --- 최종 요약 ---
    print("\n=============================================")
    print("=== Initial Script Generation Finished ===")
    print("=============================================")
    if successful_scripts:
        print("Successfully generated scripts (ready for image URL population):")
        for script in successful_scripts:
            print(f"- {script}")
    if failed_papers:
        print("\nFailed to process papers:")
        for paper in failed_papers:
            print(f"- {paper}")

    print("\nNext Step: AI Agent to populate 'bg_image_url' in the generated scripts and then run video_generator.py for each.")


if __name__ == '__main__':
    # content_processor.py에서 필요했던 json과 re 모듈을 여기서도 임포트
    import json
    import re
    main()
