import os
import json
import re
import boto3
import time
from dotenv import load_dotenv
from duckduckgo_search import DDGS

load_dotenv()
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
    raise ValueError("환경 변수(AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)가 설정되지 않았습니다.")

bedrock = boto3.client(
    service_name='bedrock-runtime',
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

def extract_json_from_text(text):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0)
    return None

def generate_keywords(game_name="몬스터헌터"):
    prompt = f"""
    다음 게임 '{game_name}'에 대한 리뷰를 검색하려고 하는데 한국 웹사이트에서 어떤 검색 키워드로 검색하면 잘 나올 지 5개 생성해줘. 반드시 5개를 생성해
    참고로 해당 게임의 은어로 쓰이는 단어도 고려해줘. 리뷰라는 단어 뿐 아니라 후기, 비평 등의 단어도 섞어서 생성해줘 
    결과를 반드시 JSON 형식으로 반환해줘:
    {{
      "keywords": ["키워드1", "키워드2", ...]
    }}
    """
    response = bedrock.invoke_model(
        modelId='amazon.nova-pro-v1:0',
        body=json.dumps({
            "messages": [{"role": "user", "content": [{"text": prompt}]}]
        }),
        contentType='application/json',
        accept='application/json'
    )
    result = json.loads(response['body'].read().decode('utf-8'))
    raw_text = result["output"]["message"]["content"][0]["text"]
    json_text = extract_json_from_text(raw_text)
    if json_text:
        return json.loads(json_text).get("keywords", [])
    raise ValueError("Bedrock 응답에서 JSON 데이터를 찾을 수 없음.")

def crawl_game_reviews(keywords, num_results_per_query=5, additional_sites=None):
    try:
        print("검색 시작...")
        reviews = []
        default_sites = ["naver.com", "inven.co.kr", "dcinside.com"]
        sites = default_sites + (additional_sites if additional_sites else [])
        sites = list(dict.fromkeys(sites))[:5]  # 최대 5개 유지

        with DDGS() as ddgs:
            for site in sites:
                # AND 연산자로 키워드 결합 (따옴표 제거)
                keyword_query = " AND ".join(keywords)
                query = f"{keyword_query} site:{site}"
                print(f"{site}에서 검색 중 (DuckDuckGo): {query}")

                try:
                    results = list(ddgs.text(query, max_results=num_results_per_query))
                    if not results:
                        print(f"경고: '{query}'에 대한 결과 없음")
                        continue

                    print(f"DuckDuckGo '{query}' 응답 일부:", json.dumps(results[:2], ensure_ascii=False, indent=2))

                    for result in results:
                        url = result["href"]
                        title = result["title"]
                        content = result["body"]
                        # 모든 키워드가 포함된 결과만 필터링
                        if all(kw.lower() in (title.lower() + content.lower()) for kw in keywords):
                            matched_keyword = " AND ".join(keywords)  # 전체 키워드 조합
                        else:
                            # 하나라도 매핑되면 해당 키워드 사용
                            matched_keyword = next((kw for kw in keywords if kw.lower() in title.lower() or kw.lower() in content.lower()), keywords[0])

                        reviews.append({
                            "url": url,
                            "date": "날짜 없음",
                            "title": title,
                            "content": content,
                            "comment": None,
                            "source": "duckduckgo",
                            "keyword": matched_keyword,
                            "site": site
                        })
                except Exception as e:
                    print(f"검색 에러: {e} - 쿼리: {query}")
                
                time.sleep(5)  # 사이트별 5초 대기

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
        keywords = generate_keywords("몬스터헌터")[:5]
        print("기본 사이트:", ["naver.com", "inven.co.kr", "dcinside.com"])
        print("생성된 키워드:", keywords)
        additional_sites = ["ruliweb.com", "gamemeca.com"]
        crawl_game_reviews(keywords, num_results_per_query=10, additional_sites=additional_sites)
    except Exception as e:
        print(f"메인 실행 중 오류 발생: {e}")