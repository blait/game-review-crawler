import os
import json
import re
import requests
import boto3
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()
SERP_API_KEY = os.getenv("SERP_API_KEY")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

if not SERP_API_KEY or not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
    raise ValueError("환경 변수(SERP_API_KEY, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)가 설정되지 않았습니다.")

# Bedrock 클라이언트 초기화
bedrock = boto3.client(
    service_name='bedrock-runtime',
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

def extract_json_from_text(text):
    """Bedrock 응답에서 JSON 부분만 추출하는 함수"""
    match = re.search(r"\{.*\}", text, re.DOTALL)  # `{`로 시작하고 `}`로 끝나는 JSON 부분 찾기
    if match:
        return match.group(0)  # JSON 부분만 리턴
    return None  # JSON이 없으면 None 리턴

def generate_review_sites():
    """Bedrock Nova Pro 모델로 게임 리뷰 관련 유명 사이트 목록 생성"""
    prompt = """
    게임 리뷰와 관련된 유명 웹사이트 도메인 5개를 생성해줘. 
    예: naver.com, inven.co.kr, gamespot.com 같은 형식.
    결과를 반드시 JSON 형식으로 반환해줘:
    {
      "sites": ["site1", "site2", ...]
    }
    """

    response = bedrock.invoke_model(
        modelId='amazon.nova-pro-v1:0',
        body=json.dumps({
            "messages": [{
                "role": "user",
                "content": [{"text": prompt}]
            }]
        }),
        contentType='application/json',
        accept='application/json'
    )

    # Bedrock 응답 파싱
    result = json.loads(response['body'].read().decode('utf-8'))
    raw_text = result["output"]["message"]["content"][0]["text"]

    # JSON 부분만 추출
    json_text = extract_json_from_text(raw_text)
    if json_text:
        sites_data = json.loads(json_text)
        return sites_data.get("sites", [])  # sites 리스트 반환
    else:
        raise ValueError("Bedrock 응답에서 JSON 데이터를 찾을 수 없음.")

def generate_keywords(game_name="로드나인"):
    """Bedrock Nova Pro 모델로 게임 리뷰 관련 검색 키워드 생성"""
    prompt = f"""
    다음 게임 '{game_name}'에 대한 리뷰를 검색하려고 하는데 한국 웹사이트에서 어떤 검색 키워드로 검색하면 잘 나올 지 5개 생성해줘. 참고로 해당 게임의 은어로 쓰이는 단어도 고려해줘. 리뷰라는 단어 뿐 아니라 후기, 비평 등의 단어도 섞어서 생성해줘 
    결과를 반드시 JSON 형식으로 반환해줘:
    {{
      "keywords": ["키워드1", "키워드2", ...]
    }}
    """

    response = bedrock.invoke_model(
        modelId='amazon.nova-pro-v1:0',
        body=json.dumps({
            "messages": [{
                "role": "user",
                "content": [{"text": prompt}]
            }]
        }),
        contentType='application/json',
        accept='application/json'
    )

    # Bedrock 응답 파싱
    result = json.loads(response['body'].read().decode('utf-8'))
    raw_text = result["output"]["message"]["content"][0]["text"]

    # JSON 부분만 추출
    json_text = extract_json_from_text(raw_text)
    if json_text:
        keywords_data = json.loads(json_text)
        return keywords_data.get("keywords", [])  # keywords 리스트 반환
    else:
        raise ValueError("Bedrock 응답에서 JSON 데이터를 찾을 수 없음.")

def crawl_game_reviews(sites, keywords, num_results_per_query=5, engines=["google"]):
    """SerpAPI를 사용하여 검색 결과 크롤링"""
    try:
        print("검색 시작...")
        reviews = []

        for engine in engines:
            for site in sites:
                for keyword in keywords:
                    query = f"{keyword} site:{site}"
                    print(f"{site}에서 '{keyword}' 검색 중 (엔진: {engine})...")
                    params = {
                        "q": query,
                        "api_key": SERP_API_KEY,
                        "num": num_results_per_query,
                        "engine": engine
                    }
                    response = requests.get("https://serpapi.com/search", params=params)
                    response.raise_for_status()
                    
                    data = response.json()
                    organic_results = data.get("organic_results", [])

                    print(f"{engine} '{query}' 응답 일부:", json.dumps(organic_results[:2], indent=2))

                    for result in organic_results:
                        url = result.get("link", "N/A")
                        title = result.get("title", "제목 없음")
                        snippet = result.get("snippet", "내용 없음")
                        date = result.get("date", "날짜 없음")

                        reviews.append({
                            "url": url,
                            "date": date,
                            "title": title,
                            "content": snippet,
                            "comment": None,
                            "source": engine,
                            "keyword": keyword,
                            "site": site
                        })

        output_file = "game_reviews_keywords_with_sites.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(reviews, f, ensure_ascii=False, indent=2)

        print(f"검색 완료! 결과가 {output_file}에 저장되었습니다.")
        print(f"총 {len(reviews)}개의 리뷰 수집됨.")
        return reviews

    except Exception as e:
        print(f"에러 발생: {e}")
        return []

if __name__ == "__main__":
    try:
        sites = generate_review_sites()
        keywords = generate_keywords("로드나인")
        print("생성된 사이트:", sites)
        print("생성된 키워드:", keywords)
        crawl_game_reviews(sites, keywords, num_results_per_query=5, engines=["google"])
    except Exception as e:
        print(f"메인 실행 중 오류 발생: {e}")