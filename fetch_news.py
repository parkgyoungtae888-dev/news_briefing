# ===== 뉴스 최신 글 가져오기 =====
# 하는 일: settings.json에 적힌 RSS 주소(뉴스 사이트의 "새 글 목록" 파일)를 열어서
#          언론사마다 최신 글 3개의 제목, 링크, 날짜만 골라 JSON 모양으로 화면에 보여줘요.
# 실행 방법: 이 폴더에서 터미널을 열고  python fetch_news.py  라고 입력해요.
# 설치할 것은 없어요. 아래에서 불러오는 도구는 모두 Python에 처음부터 들어 있어요.

# ===== 1. 필요한 도구 불러오기 =====
import json                      # JSON(자료를 { "이름": 값 } 모양으로 적는 방식)을 읽고 쓰는 도구
import sys                       # 화면 출력 설정을 바꾸는 도구
import urllib.request            # 인터넷 주소를 열어서 내용을 받아오는 도구
import xml.etree.ElementTree as ET   # RSS(XML, <태그>로 감싼 글)를 읽어서 나눠 주는 도구
from datetime import datetime, timezone, timedelta   # 날짜와 시간대(한국 시간 등)를 다루는 도구
from email.utils import parsedate_to_datetime   # "Fri, 06 Nov 2026 ..." 같은 날짜 글자를 진짜 날짜로 바꿔 주는 도구
from pathlib import Path         # 파일 위치를 다루는 도구

# ===== 2. 바꿔 쓸 수 있는 값 =====
# ✏️ 1) 언론사마다 몇 개씩 가져올지: 숫자만 바꾸면 돼요
HOW_MANY = 3

# 한국 시간(세계 표준시보다 9시간 빠름). 언론사마다 시간 적는 방식이 달라서 한국 시간으로 맞춰요.
KOREA_TIME = timezone(timedelta(hours=9))

# 윈도우 터미널에서 한글이 깨지지 않게, 화면 출력을 UTF-8(전 세계 글자를 다 쓸 수 있는 방식)로 바꿔요.
# (창 없이 실행될 때는 화면 출력 통로가 없어서(None) 건너뛰어요)
if sys.stdout is not None:
    sys.stdout.reconfigure(encoding="utf-8")

# 언론사마다 날짜를 적는 태그 이름이 달라요.
#  - 보통 RSS: <pubDate>Fri, 06 Nov 2026 20:08:00 +0900</pubDate>
#  - 경향신문: <dc:date>2026-11-06T20:08:00+09:00</dc:date>
# "dc:"는 추가 규칙 묶음(Dublin Core)에서 온 태그라는 표시예요.
# Python은 이걸 아래처럼 긴 주소를 붙인 이름으로 알아봐요.
DC_DATE_TAG = "{http://purl.org/dc/elements/1.1/}date"


# ===== 3. 설정 파일 읽기 =====
def load_settings():
    """settings.json을 읽어서 Python이 쓰기 좋은 모양(사전, dict)으로 돌려줘요."""
    # 이 파이썬 파일이 있는 폴더에서 settings.json을 찾아요.
    # (그래야 어느 폴더에서 실행해도 같은 파일을 찾을 수 있어요)
    settings_path = Path(__file__).parent / "settings.json"
    with open(settings_path, encoding="utf-8") as file:
        return json.load(file)


# ===== 4. RSS 주소 열어서 내용 받아오기 =====
def download(url):
    """주소를 열고, 받은 내용을 그대로 돌려줘요."""
    # 어떤 사이트는 "누가 왔는지" 이름표(User-Agent)가 없으면 막아요. 그래서 이름표를 붙여요.
    request = urllib.request.Request(url, headers={"User-Agent": "news-briefing/1.0"})
    # timeout=20: 20초 안에 답이 없으면 기다리지 않고 멈춰요 (무한정 멈춰 있지 않게).
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read()


# ===== 5. 날짜를 보기 좋게 바꾸기 =====
def to_korea_time(date_text):
    """날짜 글자를 '2026-11-06 20:18' (한국 시간) 모양으로 바꿔요.
    날짜가 없으면 None(JSON에서는 null, "값 없음"이라는 뜻)을 돌려줘요."""
    if not date_text:
        return None
    try:
        # 1번 방법: '2026-11-06T20:08:00+09:00' 모양 (경향신문 dc:date)
        date = datetime.fromisoformat(date_text)
    except ValueError:
        try:
            # 2번 방법: 'Fri, 06 Nov 2026 11:18:56 GMT' 모양 (보통 RSS의 pubDate)
            date = parsedate_to_datetime(date_text)
        except (TypeError, ValueError):
            # 둘 다 아니면 멈추지 말고 받은 글자를 그대로 보여줘요.
            return date_text
    # 한국 시간으로 바꾸고, 보기 쉬운 모양으로 적어요.
    return date.astimezone(KOREA_TIME).strftime("%Y-%m-%d %H:%M")


# ===== 6. RSS에서 최신 글 골라내기 =====
def latest_articles(rss_content, how_many):
    """RSS 내용에서 기사(<item>)를 찾아 제목, 링크, 날짜만 뽑아요."""
    root = ET.fromstring(rss_content)       # RSS 글을 읽어서 <태그> 나무 구조로 만들어요
    articles = []
    # .iter("item"): RSS 안의 모든 <item>(기사 1개)을 위에서부터 차례로 꺼내요.
    for item in root.iter("item"):
        articles.append({
            # findtext: 태그 안의 글자를 꺼내요. 없으면 "" (빈칸)을 넣어요. strip(): 앞뒤 빈칸 지우기
            "title": item.findtext("title", "").strip(),
            "link": item.findtext("link", "").strip(),
            # <pubDate>를 먼저 찾고, 없으면 <dc:date>를 찾아요. 둘 다 없으면 빈칸이에요.
            "date": to_korea_time(
                (item.findtext("pubDate") or item.findtext(DC_DATE_TAG) or "").strip()
            ),
        })
    # 날짜가 늦은(최신) 순서로 정렬해요.
    # 날짜 모양이 "2026-11-06 20:18"이라 글자 순서대로 정렬해도 시간 순서와 같아요.
    # 날짜가 없는 글은 "" 로 쳐서 뒤로 보내요. 모두 날짜가 없으면(한겨레처럼)
    # 순서가 그대로 남는데, RSS는 원래 최신 글이 맨 위에 있어서 괜찮아요.
    articles.sort(key=lambda article: article["date"] or "", reverse=True)
    return articles[:how_many]   # 앞에서부터 how_many개만 잘라요


# ===== 7. 전체 순서 =====
def main():
    settings = load_settings()
    result = []

    # settings.json의 feeds에 적힌 언론사를 하나씩 돌아가며 처리해요.
    for feed in settings["feeds"]:
        try:
            content = download(feed["url"])
            articles = latest_articles(content, HOW_MANY)
            result.append({"source": feed["name"], "articles": articles})
        except Exception as error:
            # 한 곳이 안 열려도 나머지는 계속 보여주려고, 오류를 기록만 하고 넘어가요.
            result.append({"source": feed["name"], "error": str(error)})

    # 결과를 JSON 모양으로 화면에 보여줘요.
    # ensure_ascii=False: 한글을 \uXXXX 같은 암호 대신 한글 그대로 보여줘요.
    # indent=2: 두 칸씩 들여 써서 눈으로 읽기 쉽게 해요.
    json_text = json.dumps(result, ensure_ascii=False, indent=2)
    print(json_text)

    # 같은 내용을 news.json 파일로도 저장해요.
    # 터미널 글은 창을 닫으면 사라지지만, 파일은 남아서 VS Code에서 언제든 열어 볼 수 있어요.
    output_path = Path(__file__).parent / "news.json"
    output_path.write_text(json_text, encoding="utf-8")
    print(f"\n저장했어요: {output_path}")


# 이 파일을 직접 실행했을 때만 main()을 시작해요.
# (다른 파일에서 이 파일의 도구만 빌려 쓸 때는 자동으로 실행되지 않게 하려는 거예요)
if __name__ == "__main__":
    main()
