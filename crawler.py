import json
import urllib.request
import xml.etree.ElementTree as ET
import os
import re

ARXIV_API_URL = 'http://export.arxiv.org/api/query'

def fetch_latest_paper(topic: str):
    """
    주어진 주제에 대해 arXiv에서 가장 최신 논문을 가져옵니다.
    """
    print(f"Fetching latest paper for topic: {topic}...")
    
    search_query = f'all:"{topic}"'
    params = {
        'search_query': search_query,
        'start': '0',
        'max_results': '1',
        'sortBy': 'submittedDate',
        'sortOrder': 'descending'
    }
    
    query_url = f"{ARXIV_API_URL}?{urllib.parse.urlencode(params)}"
    
    try:
        with urllib.request.urlopen(query_url) as response:
            if response.status != 200:
                print(f"Error: Failed to fetch data for topic '{topic}'. Status: {response.status}")
                return None
            
            xml_data = response.read().decode('utf-8')
            return xml_data
            
    except Exception as e:
        print(f"An error occurred while fetching data for '{topic}': {e}")
        return None

def parse_arxiv_xml(xml_data: str):
    """
    arXiv API로부터 받은 XML 데이터를 파싱하여 논문 정보를 반환합니다.
    """
    if not xml_data:
        return None
        
    root = ET.fromstring(xml_data)
    entry = root.find('{http://www.w3.org/2005/Atom}entry')
    
    if entry is None:
        print("No paper found in the API response.")
        return None
        
    # 네임스페이스
    ns = {'atom': 'http://www.w3.org/2005/Atom'}
    
    title = entry.find('atom:title', ns).text.strip()
    # arXiv ID는 URL의 마지막 부분에 있습니다.
    arxiv_id_url = entry.find('atom:id', ns).text
    arxiv_id = os.path.basename(arxiv_id_url)
    
    summary = entry.find('atom:summary', ns).text.strip()
    
    # 제목과 요약에서 줄바꿈 문자를 공백으로 치환하여 정리합니다.
    title = re.sub(r'\s+', ' ', title)
    summary = re.sub(r'\s+', ' ', summary)
    
    return {'id': arxiv_id, 'title': title, 'summary': summary}

def main():
    """
    설정 파일에서 주제를 읽어 각 주제별 최신 논문을 크롤링하고 파일로 저장합니다.
    """
    try:
        with open('crawler_config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("Error: crawler_config.json not found.")
        return
        
    topics = config.get('topics', [])
    if not topics:
        print("No topics found in crawler_config.json.")
        return

    print("--- Starting arXiv Crawler ---")
    
    # 크롤링 결과를 저장할 디렉토리 생성
    output_dir = "crawled_papers"
    os.makedirs(output_dir, exist_ok=True)

    for topic in topics:
        xml_response = fetch_latest_paper(topic)
        if xml_response:
            paper_info = parse_arxiv_xml(xml_response)
            if paper_info:
                # 파일 이름으로 부적합한 문자를 제거합니다.
                safe_topic = re.sub(r'\W+', '', topic)
                filename = f"{safe_topic}_{paper_info['id']}.txt"
                filepath = os.path.join(output_dir, filename)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(f"Title: {paper_info['title']}\n\n")
                    f.write(f"Abstract:\n{paper_info['summary']}")
                
                print(f"Successfully saved paper to {filepath}")
    
    print("\n--- Crawler Finished ---")

if __name__ == '__main__':
    main()
