import sys
import json
import os
import textwrap




try:
    import requests
except ImportError:
    print("Required library 'requests' is not installed. Please run 'pip install requests'")
    sys.exit(1)

# --- Ollama 설정 ---
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3"
# --------------------

def generate_script_with_ollama(text_content: str, source_filename: str) -> dict:
    """Ollama API를 호출하여 텍스트 콘텐츠로부터 대화 형식의 스크립트를 생성합니다."""
    print(f"Contacting Ollama with model '{OLLAMA_MODEL}' to generate script...")
    title_from_filename = os.path.splitext(source_filename)[0]
    title = f"{title_from_filename}_Ollama"
    
    system_prompt = textwrap.dedent(f"""
        You are an expert scriptwriter for a tech YouTube channel. Your task is to convert the following research paper abstract into a short, engaging conversational script between two hosts, Alex and Ben.
        RULES:
        1. The entire output MUST be a single, valid JSON object. Do not include any text before or after the JSON object.
        2. The JSON object must have three keys: "title", "characters", and "dialogue".
        3. The "title" key's value must be exactly: "{title}"
        4. The "characters" key's value must be an array of two objects.
           - The first object is for "Alex", and must have "name": "Alex" and "image_url": "https://placehold.co/400x400/3E4A89/FFFFFF/png?text=Alex".
           - The second object is for "Ben", and must have "name": "Ben" and "image_url": "https://placehold.co/400x400/A84834/FFFFFF/png?text=Ben".
        5. The "dialogue" key's value must be an array of objects, where each object has a "speaker" ("Alex" or "Ben"), a "line" (their dialogue), and a "keywords" field.
        6. The "keywords" field must be an array of 1 to 3 relevant nouns or technical terms from the dialogue line for image searches.
        7. The dialogue should be a conversation that explains the key points of the abstract in an easy-to-understand way.
        8. The conversation should have between 4 and 6 turns.
        Here is the abstract:
        ---
        {text_content}
        ---
        Now, generate the JSON output based on these rules.
    """).strip()

    print(f"--- PROMPT FOR {source_filename} ---\n{system_prompt}\n--------------------")
    
    payload = {"model": OLLAMA_MODEL, "prompt": system_prompt, "format": "json", "stream": False}

    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=120)
        response.raise_for_status()
        response_json = response.json()
        script_json_str = response_json.get("response")
        
        print(f"--- OLLAMA RESPONSE ---\n{script_json_str}\n--------------------")

        if not script_json_str:
            print("Error: Ollama returned an empty response.")
            return None
        
        script_data = json.loads(script_json_str)
        print("Ollama script generation successful.")
        return script_data
    except requests.exceptions.RequestException as e:
        print(f"Error contacting Ollama API: {e}")
        return None
    except json.JSONDecodeError:
        print(f"Error: Failed to decode JSON from Ollama's response.")
        return None



def process_text_to_script(input_filepath: str, output_filepath: str) -> bool:
    """텍스트를 읽고, LLM으로 대본을 생성하고, 이미지를 스크랩한 후 JSON으로 저장합니다."""
    print(f"--- Starting Content Processing for {input_filepath} ---")
    try:
        with open(input_filepath, 'r', encoding='utf-8') as f:
            source_text = f.read()
    except FileNotFoundError:
        print(f"Error: Input file not found at {input_filepath}")
        return False

    script_data = generate_script_with_ollama(source_text, os.path.basename(input_filepath))
    if not script_data:
        return False



    try:
        with open(output_filepath, 'w', encoding='utf-8') as f:
            json.dump(script_data, f, ensure_ascii=False, indent=2)
        print(f"\n--- Success! Script with image URLs saved as {output_filepath} ---")
        return True
    except Exception as e:
        print(f"Error writing to output file: {e}")
        return False

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 content_processor.py <input_text_file_path>")
        sys.exit(1)
    
    input_filepath = sys.argv[1]
    base_filename = os.path.basename(input_filepath)
    name_without_ext = os.path.splitext(base_filename)[0]
    output_filepath = f"script_{name_without_ext}.json"
    
    if not process_text_to_script(input_filepath, output_filepath):
        sys.exit(1)
