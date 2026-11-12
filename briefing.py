# ===== 뉴스 브리핑 만들기 =====
# 하는 일:
#   1) settings.json에 적힌 모든 RSS(뉴스 사이트의 "새 글 목록")에서 기사를 가져와요.
#   2) 제목이나 소개문에 키워드(드론, 하이닉스, 인공지능 등)가 들어간 기사를
#      키워드마다 돌아가며 골고루 고르고, 모자라면 최신 기사로 채워서 최대 5개를 만들어요.
#   3) 기사마다 어떤 키워드가 걸렸는지 적어요.
#   4) Gemini(구글의 AI)에게 기사마다 세 줄 요약을 부탁해요.
#      키가 없거나 Gemini가 끝내 실패하면, summarizer.py가 소개문 앞 문장으로 대신 채워요.
#   5) 결과를 news.json(자료 파일)과 index.html(브라우저로 보는 화면)로 저장해요.
#   기사 본문은 가져오지 않아요. RSS에 들어 있는 제목·소개문·링크·날짜만 써요.
#   그래서 Gemini도 제목과 짧은 소개문만 보고 요약해요.
#
# 실행 방법: 이 폴더에서 터미널을 열고  python briefing.py  라고 입력해요.
# 설치할 것은 없어요. 모두 Python에 처음부터 들어 있는 도구예요.
#
# 준비물: .env 파일에 아래처럼 Gemini API 키(AI를 쓰기 위한 비밀번호)를 한 줄 적어 두세요.
#     GEMINI_API_KEY=여기에_발급받은_키
#   키는 Google AI Studio(aistudio.google.com)에서 "Get API key"를 누르면 받을 수 있어요.
#   .env는 .gitignore에 적혀 있어서 GitHub에 올라가지 않아요. 키를 코드에 직접 쓰지 마세요.

# ===== 1. 필요한 도구 불러오기 =====
import html                      # "&amp;"를 "&"로 되돌리거나, 반대로 화면에 안전하게 바꾸는 도구
import json                      # JSON(자료를 { "이름": 값 } 모양으로 적는 방식)을 읽고 쓰는 도구
import os                        # 컴퓨터의 환경 변수(프로그램 밖에 저장된 설정 값)를 읽는 도구
import re                        # 글자 안에서 정해진 모양(예: <태그>)을 찾아 지우는 도구
import time                      # 잠깐 기다리기(다시 시도하기 전 쉬기)에 쓰는 도구
import urllib.error              # 인터넷 요청이 실패했을 때 그 이유를 알려 주는 도구
import urllib.request            # 인터넷에 요청을 보내는 도구 (Gemini 부를 때 써요)
import xml.etree.ElementTree as ET   # RSS(XML, <태그>로 감싼 글)를 읽어서 나눠 주는 도구
from datetime import datetime
from pathlib import Path         # 파일 위치를 다루는 도구

# 앞에서 만든 fetch_news.py의 도구를 빌려 써요. (같은 코드를 두 번 쓰지 않으려고)
#  - load_settings: settings.json 읽기
#  - download: 인터넷 주소 열기
#  - to_korea_time: 날짜를 한국 시간 "2026-11-06 20:18" 모양으로 바꾸기
#  - DC_DATE_TAG, KOREA_TIME: 경향신문 날짜 태그 이름, 한국 시간대
from fetch_news import load_settings, download, to_korea_time, DC_DATE_TAG, KOREA_TIME
# summarizer.py의 summarize: Gemini가 안 될 때, 소개문에서 앞 문장 3개를 골라 대신 채우기
from summarizer import summarize as summarize_from_rss

# ===== 2. 바꿔 쓸 수 있는 값 =====
# ✏️ 1) 브리핑에 넣을 기사 수(최대): 숫자만 바꾸면 돼요
MAX_ARTICLES = 5
# ✏️ 2) 저장할 파일 이름: 글자만 바꾸면 돼요
JSON_FILE = "news.json"
HTML_FILE = "index.html"
# ✏️ 3) 화면 맨 위 제목: 글자만 바꾸면 돼요
PAGE_TITLE = "경제·IT 아침 브리핑"
# ✏️ 4) 맨 아래 안내 문구: 글자만 바꾸면 돼요
FOOTER_TEXT = "AI 요약은 틀릴 수 있음. 자세한 내용은 원문을 확인해 주세요."
# ✏️ 5) 쓸 Gemini 모델 이름: 앞에서부터 차례로 써 보고, 안 되면 다음 모델로 넘어가요.
#    (2026-11-07 시험: 3.5-flash 3.6초, 3.5-flash-lite 1.3초로 답함. 3.8-flash는 30초 넘게 답이 없었어요)
GEMINI_MODELS = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.8-flash"]
# ✏️ 6) 기다리는 시간과 다시 해 보는 횟수: 숫자만 바꾸면 돼요
GEMINI_TIMEOUT_SECONDS = 30   # 답을 최대 몇 초 기다릴지
RETRY_TIMES = 2               # 한 모델로 몇 번까지 해 볼지
RETRY_WAIT_SECONDS = 3        # 다시 하기 전 몇 초 쉴지
# ✏️ 7) Gemini에게 보낼 부탁 문장(프롬프트). 맨 아래에 기사 정보가 자동으로 붙어요
SUMMARY_PROMPT = """아래 기사 정보만 보고 한국어로 세 줄 요약을 써 줘.
- 각 줄은 한 문장, 줄 앞에 "- " 를 붙인다
- 기사 정보에 없는 내용, 숫자, 이름은 절대 쓰지 않는다
- 정보가 부족하면 마지막 줄에 "- 자세한 내용은 원문 확인 필요" 라고 쓴다

[기사 정보]
제목: {title}
언론사: {source}
소개문: {summary}"""


# ===== 3. 소개문 깨끗하게 만들기 =====
def clean_text(text):
    """소개문 안의 <태그>와 특수 표기를 지우고 글자만 남겨요.
    (한겨레 소개문에는 사진을 보여주는 <table>, <img> 같은 태그가 들어 있어서,
     태그를 지우지 않으면 키워드 찾기와 요약이 엉뚱하게 될 수 있어요)"""
    text = re.sub(r"<[^>]+>", " ", text or "")   # <...> 모양을 모두 빈칸으로 바꿔요
    text = html.unescape(text)                   # &amp; → & 처럼 원래 글자로 되돌려요
    return re.sub(r"\s+", " ", text).strip()     # 여러 칸 빈칸을 한 칸으로 줄이고 앞뒤 빈칸 지우기


# ===== 4. 한 언론사의 기사 전부 읽기 =====
def read_feed(feed):
    """RSS 주소 하나를 열어서, 그 안의 기사를 모두 목록으로 돌려줘요."""
    root = ET.fromstring(download(feed["url"]))
    articles = []
    # enumerate: 기사에 0, 1, 2 ... 순서 번호를 같이 붙여 줘요.
    # 날짜가 없는 기사(한겨레)는 이 번호(위에 있을수록 최신)로 순서를 정하려고 남겨 둬요.
    for position, item in enumerate(root.iter("item")):
        articles.append({
            "title": clean_text(item.findtext("title")),
            "link": (item.findtext("link") or "").strip(),
            # <pubDate>를 먼저 찾고, 없으면 <dc:date>를 찾아요. 둘 다 없으면 날짜 없음(None)
            "date": to_korea_time((item.findtext("pubDate") or item.findtext(DC_DATE_TAG) or "").strip()),
            "source": feed["name"],
            # 소개문은 키워드 찾기와 요약에만 쓰고, 결과 파일에는 넣지 않아요.
            "_summary": clean_text(item.findtext("description")),
            "_position": position,
        })
    return articles


# ===== 5. 키워드 찾기 =====
def find_keywords(article, keywords):
    """제목이나 소개문에 들어 있는 키워드만 골라서 목록으로 돌려줘요. 없으면 빈 목록 []."""
    text = (article["title"] + " " + article["_summary"]).lower()   # lower(): 영어 대소문자 구분 없이 찾기
    return [keyword for keyword in keywords if keyword.lower() in text]


# ===== 6. 최신 순서 정하기 =====
def newest_first_key(article):
    """정렬할 때 쓰는 기준이에요. 날짜가 있는 기사가 먼저, 그 안에서는 최신 순서예요.
    날짜가 없는 기사는 뒤로 보내고, RSS에서 위에 있던 순서(최신 순)를 지켜요."""
    has_date = article["date"] is not None
    # 날짜 "2026-11-06 20:18"을 숫자로 바꿔요. 숫자가 클수록 최신이에요.
    # 앞에 마이너스(-)를 붙이면 작은 값부터 정렬할 때 최신이 앞으로 와요.
    timestamp = datetime.strptime(article["date"], "%Y-%m-%d %H:%M").timestamp() if has_date else 0
    return (not has_date, -timestamp, article["_position"])


# ===== 6-1. 주제(키워드)별로 골고루 고르기 =====
def pick_balanced(articles, keywords, how_many):
    """키워드마다 돌아가며 한 개씩 골라요. (카드 게임에서 한 장씩 나눠 주듯이)
    예) 키워드가 드론·하이닉스·인공지능이면
        1바퀴: 드론 최신 1개 → 하이닉스 최신 1개 → 인공지능 최신 1개
        2바퀴: 드론 다음 1개 → 하이닉스 다음 1개 → ...
    한 기사에 키워드가 여러 개 걸려 있으면 한 번만 들어가요.
    키워드 기사가 모자라면, 키워드 없는 최신 기사로 채워요."""
    # 1단계: 키워드마다 "그 키워드가 들어간 기사 목록"을 최신 순으로 만들어요.
    by_keyword = {
        keyword: sorted([a for a in articles if keyword in a["matched_keywords"]], key=newest_first_key)
        for keyword in keywords
    }

    picked = []
    picked_links = set()          # 이미 고른 기사의 링크 (같은 기사를 두 번 넣지 않으려고)

    def add(article):
        if article["link"] not in picked_links:
            picked.append(article)
            picked_links.add(article["link"])

    # 2단계: 키워드를 돌아가며 한 개씩 골라요. 다 고르거나, 더 고를 기사가 없으면 멈춰요.
    while len(picked) < how_many:
        added_this_round = False
        for keyword in keywords:
            # 이 키워드 목록에서 아직 안 고른 기사 중 가장 최신 것을 찾아요.
            for article in by_keyword[keyword]:
                if article["link"] not in picked_links:
                    add(article)
                    added_this_round = True
                    break
            if len(picked) >= how_many:
                break
        if not added_this_round:   # 어느 키워드에도 남은 기사가 없으면 그만 돌아요
            break

    # 3단계: 그래도 모자라면 키워드 없는 기사를 최신 순으로 채워요.
    others = sorted([a for a in articles if not a["matched_keywords"]], key=newest_first_key)
    for article in others:
        if len(picked) >= how_many:
            break
        add(article)
    return picked


# ===== 7. .env에서 API 키 읽기 =====
def load_api_key():
    """.env 파일에서 GEMINI_API_KEY=... 줄을 찾아 키를 돌려줘요. 없으면 None(값 없음).
    (python-dotenv 같은 설치 도구 없이, 파일을 한 줄씩 직접 읽어요)"""
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        # utf-8-sig: 메모장이 파일 맨 앞에 몰래 붙이는 표시(BOM)가 있어도 잘 읽게 해요.
        for line in env_path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            # 빈 줄이나 #으로 시작하는 메모 줄은 건너뛰어요.
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)       # 첫 번째 = 를 기준으로 이름과 값을 나눠요
            if name.strip() == "GEMINI_API_KEY":
                # 값 양쪽에 따옴표("...")가 있으면 떼어 내요.
                return value.strip().strip('"').strip("'") or None
    # .env에 없으면 컴퓨터 환경 변수에서도 한 번 찾아봐요.
    return os.environ.get("GEMINI_API_KEY") or None


# ===== 8. Gemini에게 세 줄 요약 한 번 부탁하기 =====
def ask_gemini(article, api_key, model):
    """기사 정보를 Gemini(model)에 한 번 보내서 세 줄 요약(글자 목록)을 받아요."""
    prompt = SUMMARY_PROMPT.format(
        title=article["title"],
        source=article["source"],
        summary=article["_summary"] or "(소개문 없음)",
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    # Gemini가 정해 둔 모양대로 부탁 내용을 JSON으로 싸요.
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,                                   # data를 넣으면 "보내기(POST)" 요청이 돼요
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,               # 키는 주소가 아니라 머리말(header)에 넣어서 기록에 덜 남게 해요
        },
    )
    with urllib.request.urlopen(request, timeout=GEMINI_TIMEOUT_SECONDS) as response:
        answer = json.loads(response.read())
    # 답장 속 깊숙이 있는 글자를 꺼내요: 후보(candidates) 1번 → 내용(content) → 조각(parts) → 글자(text)
    text = "".join(part.get("text", "") for part in answer["candidates"][0]["content"]["parts"])
    # "- "로 시작하는 줄만 골라서, 앞의 "- "를 떼고 세 줄만 남겨요.
    lines = [line.strip()[2:].strip() for line in text.splitlines() if line.strip().startswith("- ")]
    if not lines:
        raise ValueError("요약 모양이 예상과 달라요")
    return lines[:3]


# ===== 9. 요약 붙이기 (Gemini → 안 되면 소개문으로 대신) =====
def add_summaries(articles, api_key):
    """기사마다 summary(세 줄 목록)와 summary_by(누가 요약했는지)를 붙여요.
    - summary_by "gemini": Gemini가 요약했어요
    - summary_by "rss": 키가 없거나 Gemini가 실패해서, 소개문 앞 문장으로 대신 채웠어요"""
    working_models = list(GEMINI_MODELS)   # 아직 쓸 수 있는 모델 목록 (끝내 실패한 모델은 빼요)

    for number, article in enumerate(articles, start=1):
        print(f"요약 중 {number}/{len(articles)}: {article['title'][:30]}")
        summary = None

        # 1단계: 키가 있으면, 쓸 수 있는 모델을 차례로 써 봐요.
        for model in list(working_models) if api_key else []:
            for attempt in range(1, RETRY_TIMES + 1):
                try:
                    summary = ask_gemini(article, api_key, model)
                    break                                   # 성공하면 다시 하기를 멈춰요
                except urllib.error.HTTPError as error:
                    reason = f"오류 {error.code}"
                    # 400·401·403: 키가 틀렸어요. 몇 번을 다시 해도 똑같아서 Gemini를 아예 그만 써요.
                    if error.code in (400, 401, 403):
                        print(f"  · API 키를 확인해 주세요({reason}). 이번엔 소개문으로 채워요.")
                        api_key = None
                        working_models.clear()
                        break
                    # 404: 이 모델은 없어요. 다시 해도 소용없으니 바로 다음 모델로 넘어가요.
                    if error.code == 404:
                        break
                except Exception as error:
                    reason = str(error)                     # 시간 초과 등
                print(f"  · {model} {attempt}번째 실패({reason})")
                if attempt < RETRY_TIMES:
                    time.sleep(RETRY_WAIT_SECONDS)          # 서버가 붐빌 수 있어서 잠깐 쉬었다가 다시 해요
            # 성공했거나, 키가 틀려서 Gemini를 그만 쓰기로 했으면 다음 모델로 넘어가지 않아요.
            if summary or not api_key:
                break
            # 이 모델은 끝내 안 됐어요. 다음 기사부터는 기다리지 않게 목록에서 빼요.
            if model in working_models:
                working_models.remove(model)

        # 2단계: Gemini로 못 했으면, 소개문 앞 문장으로 대신 채워요. (페이지는 꼭 만들어지게)
        if summary:
            article["summary"], article["summary_by"] = summary, "gemini"
        else:
            article["summary"], article["summary_by"] = summarize_from_rss(article["_summary"]), "rss"


# ===== 10. index.html 만들기 =====
# 화면 모양은 planner(AI 스터디 플래너)와 같은 마인크래프트풍이에요.
# 아래 HTML_TEMPLATE 안의 __이름__ 자리에 기사 내용이 채워져요.
# (CSS 안의 { } 기호와 헷갈리지 않게, f-글자 대신 바꿔 넣기(replace)를 써요)
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>__TITLE__</title>
  <!-- 이 파일은 briefing.py가 자동으로 만들어요. 직접 고치면 다음 실행 때 덮어써져요.
       제목·문구는 briefing.py 맨 위 ✏️ 표시, 모양은 briefing.py의 HTML_TEMPLATE을 고쳐 주세요. -->

  <!-- 도트 느낌 한글 글꼴(갈무리). 인터넷이 없으면 기본 글꼴로 보여요 -->
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/galmuri@latest/dist/galmuri.css">

  <style>
    /* ===== 색깔 모음 (여기 값만 바꿔도 분위기가 바뀌어요) ===== */
    :root {
      --sky: #8fd3f4;     /* 하늘색 배경 */
      --panel: #c6c6c6;   /* 카드(인벤토리 창) 회색 */
      --dark: #3f3f3f;    /* 기본 글자색 */
      --muted: #4a4a4a;   /* 조금 흐린 글자색 */
      --slot: #8b8b8b;    /* 움푹 들어간 칸 회색 */
      --deep: #373737;    /* 어두운 칸 */
      --gold: #ffff55;    /* 키워드 강조 노란색 */
      --green: #3c8527;   /* 고른 버튼 초록색 */
    }

    * { box-sizing: border-box; }

    /* ===== 바깥 배경: 하늘 + 풀밭 ===== */
    body {
      margin: 0;
      min-height: 100vh;
      padding: 32px 20px 96px;     /* 아래쪽은 풀밭 자리 */
      background: var(--sky);
      color: var(--dark);
      font-family: "Galmuri11", "Galmuri9", "DungGeunMo", "Malgun Gothic", "Apple SD Gothic Neo", monospace;
    }

    /* 화면 맨 아래 풀밭 (잔디 한 줄 + 흙) */
    body::after {
      content: "";
      position: fixed;
      left: 0;
      right: 0;
      bottom: 0;
      height: 64px;
      background:
        conic-gradient(rgba(0, 0, 0, 0.08) 25%, transparent 0 50%, rgba(0, 0, 0, 0.08) 0 75%, transparent 0) 0 0 / 16px 16px,
        linear-gradient(#5fb23a 0 16px, #8a5a3a 16px);
      pointer-events: none;
    }

    /* ===== 전체 틀: 제목 + 두 칸 ===== */
    .wrap {
      position: relative;
      z-index: 1;
      max-width: 1040px;
      margin: 0 auto;
    }

    .top {
      display: flex;
      align-items: center;
      gap: 14px;
      margin-bottom: 20px;
    }
    .top svg { width: 48px; height: 48px; flex: none; }

    .title {
      margin: 0;
      padding: 6px 14px;
      font-size: 2rem;
      color: #fff;
      background: rgba(0, 0, 0, 0.7);   /* 캐릭터 머리 위 이름표 느낌 */
    }

    /* 컴퓨터 화면 기준: 왼쪽(브리핑 정보) / 오른쪽(기사 목록) 두 칸 */
    .columns {
      display: grid;
      grid-template-columns: 300px 1fr;
      gap: 24px;
      align-items: start;
    }

    /* ===== 카드 = 마인크래프트 인벤토리 창 ===== */
    .card {
      min-width: 0;   /* 긴 글이 있어도 칸이 화면 밖으로 늘어나지 않게 해요 */
      padding: 24px;
      background: var(--panel);
      /* 검정 바깥선 + 왼쪽 위는 밝게, 오른쪽 아래는 어둡게 (입체감) */
      box-shadow: 0 0 0 4px #000, inset 4px 4px 0 #fff, inset -4px -4px 0 #555;
    }

    /* 제목 (오른쪽으로 홈 파인 선이 이어져요) */
    .section-title {
      display: flex;
      align-items: center;
      gap: 12px;
      margin: 0 0 14px;
      font-size: 1rem;
    }
    .section-title::after {
      content: "";
      flex: 1;
      height: 4px;
      border-top: 2px solid var(--slot);
      border-bottom: 2px solid #fff;
    }

    .help {
      margin: 0;
      font-size: 0.85rem;
      line-height: 1.6;
      color: var(--muted);
    }

    /* ===== 왼쪽 칸: 수집 시각 + 언론사 ===== */
    .info {
      margin: 0 0 18px;
      padding: 10px 12px;
      font-size: 0.85rem;
      line-height: 1.8;
      color: #fff;
      background: var(--deep);
      box-shadow: inset 2px 2px 0 #1b1b1b, inset -2px -2px 0 #fff;
    }
    .info b { color: var(--gold); font-weight: 700; }

    /* ===== 버튼 = 마인크래프트 버튼 ===== */
    .filters { display: grid; gap: 8px; margin-bottom: 18px; }
    .btn {
      display: flex;
      justify-content: space-between;
      padding: 10px 14px;
      font: inherit;
      font-weight: 700;
      color: #fff;
      text-shadow: 2px 2px 0 var(--dark);
      background: var(--slot);
      border: 2px solid #000;
      box-shadow: inset 2px 2px 0 #bcbcbc, inset -2px -2px 0 #555;
      cursor: pointer;
    }
    .btn:hover { color: #ffffa0; background: #4a5d99; }
    .btn:active { box-shadow: inset 2px 2px 0 #555, inset -2px -2px 0 #bcbcbc; }
    .btn:focus-visible { outline: 3px solid #fff; outline-offset: 2px; }
    .btn[aria-pressed="true"] { background: var(--green); }   /* 지금 고른 버튼은 초록색 */
    .btn .count { color: #e0e0e0; }

    /* ===== 오른쪽 칸: 기사 목록 ===== */
    .articles { display: grid; gap: 14px; }

    /* 기사 하나 = 움푹 들어간 아이템 칸 */
    .article {
      padding: 16px;
      background: var(--slot);
      box-shadow: inset 2px 2px 0 var(--deep), inset -2px -2px 0 #fff;
      animation: drop 0.4s steps(4) both;   /* 위에서 뚝뚝 끊기며 내려와요 */
    }
    .article[hidden] { display: none; }
    @keyframes drop {
      from { opacity: 0; transform: translateY(-8px); }
      to   { opacity: 1; transform: none; }
    }

    .article h3 {
      margin: 0 0 10px;
      font-size: 1.05rem;
      line-height: 1.5;
      color: #fff;
      text-shadow: 2px 2px 0 var(--dark);
      word-break: keep-all;        /* 한글 단어가 중간에서 끊기지 않게 해요 */
      overflow-wrap: anywhere;     /* 아주 긴 단어는 그래도 줄을 바꿔서 화면 밖으로 안 나가게 해요 */
    }

    /* 키워드 = 아이템 이름표 */
    .tags { display: flex; flex-wrap: wrap; gap: 6px; margin: 0 0 10px; padding: 0; list-style: none; }
    .tag {
      padding: 2px 8px;
      font-size: 0.75rem;
      color: var(--gold);
      background: #100010;
      border: 2px solid #2a0a5e;
    }
    .tag.latest { color: #c0c0c0; }   /* 키워드 없이 최신 기사로 채운 것 */
    .tag.by { color: #55ffff; }       /* 누가 요약했는지 (AI 요약 / 소개문 발췌) */

    /* 세 줄 요약 = 채팅창 */
    .summary {
      margin: 0 0 12px;
      padding: 10px 12px 10px 28px;
      font-size: 0.9rem;
      line-height: 1.7;
      color: #fff;
      background: rgba(0, 0, 0, 0.6);
      overflow-wrap: anywhere;
    }

    .meta {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      margin: 0;
      font-size: 0.8rem;
      font-weight: 700;
      color: #fff;
      text-shadow: 1px 1px 0 var(--dark);
    }

    /* 원문 링크 = 마인크래프트 아이템 설명창 */
    .item {
      display: inline-block;
      padding: 4px 10px;
      color: #fff;
      text-decoration: none;
      text-shadow: none;
      background: #100010;
      border: 2px solid #2a0a5e;
    }
    .item:hover { color: var(--gold); }
    .item:focus-visible { outline: 3px solid #fff; outline-offset: 2px; }

    .empty {
      margin: 0;
      padding: 16px;
      color: #fff;
      background: rgba(0, 0, 0, 0.6);
    }
    .empty[hidden] { display: none; }

    /* 맨 아래 안내 = 채팅창 */
    .notice {
      margin: 20px 0 0;
      padding: 8px 12px;
      font-size: 0.8rem;
      line-height: 1.6;
      color: #fff;
      background: rgba(0, 0, 0, 0.6);
    }

    /* ===== 좁은 화면 (태블릿·폰) ===== */
    @media (max-width: 820px) {
      .columns { grid-template-columns: 1fr; }   /* 두 칸을 위아래 한 줄로 쌓아요 */
      .title { font-size: 1.5rem; }
      .filters { grid-template-columns: repeat(2, 1fr); }
    }
    @media (max-width: 420px) {
      body { padding: 20px 12px 88px; }
      .card { padding: 16px; }
      .top svg { width: 36px; height: 36px; }
      .title { font-size: 1.25rem; }
      .article { padding: 12px; }
      .btn { padding: 8px 10px; font-size: 0.85rem; }
    }

    /* 움직임 줄이기 설정을 쓰는 사람을 위한 배려 */
    @media (prefers-reduced-motion: reduce) {
      .article { animation: none; }
    }
  </style>
</head>

<body>
  <div class="wrap">

    <header class="top">
      <!-- 도트 신문 그림 (장식용이라 화면 낭독기는 건너뛰어요) -->
      <svg viewBox="0 0 16 16" shape-rendering="crispEdges" aria-hidden="true">
        <rect x="1" y="2" width="14" height="12" fill="#000"/>
        <rect x="2" y="3" width="12" height="10" fill="#f4f1e8"/>
        <rect x="3" y="4" width="10" height="2" fill="#3f3f3f"/>
        <rect x="3" y="7" width="4" height="4" fill="#8fd3f4"/>
        <rect x="8" y="7" width="5" height="1" fill="#8b8b8b"/>
        <rect x="8" y="9" width="5" height="1" fill="#8b8b8b"/>
        <rect x="8" y="11" width="3" height="1" fill="#8b8b8b"/>
      </svg>
      <h1 class="title">__TITLE__</h1>
    </header>

    <div class="columns">

      <!-- ===== 왼쪽 칸: 브리핑 정보 + 키워드 고르기 ===== -->
      <aside class="card">
        <h2 class="section-title">브리핑 정보</h2>
        <p class="info">
          수집 시각 <b>__COLLECTED__</b><br>
          언론사<br>__SOURCES__
        </p>

        <h2 class="section-title">키워드로 보기</h2>
        <!-- 버튼을 누르면 그 키워드가 들어간 기사만 보여요. data-filter 값으로 골라요 -->
        <div class="filters" id="filters">
__FILTERS__
        </div>
        <p class="help">키워드마다 돌아가며 골고루 고르고, 모자라면 최신 기사로 채웠어요.</p>
      </aside>

      <!-- ===== 오른쪽 칸: 기사 목록 ===== -->
      <main class="card">
        <h2 class="section-title">오늘의 기사</h2>
        <!-- 기사마다 data-keywords에 걸린 키워드가 적혀 있어요 (키워드 버튼이 이걸 읽어요) -->
        <div class="articles" id="articles">
__ARTICLES__
        </div>
        <p class="empty" id="empty-message" hidden>이 키워드가 들어간 기사가 없어요.</p>
        <p class="notice">__FOOTER__</p>
      </main>

    </div>
  </div>

  <script>
    /* ===== 키워드 버튼: 고른 키워드가 들어간 기사만 보여주기 ===== */
    const filterButtons = document.querySelectorAll("#filters .btn");
    const articleCards = document.querySelectorAll("#articles .article");
    const emptyMessage = document.getElementById("empty-message");
    let currentFilter = "all";   // 지금 고른 키워드 ("all" = 전체)

    function showArticles(chosenFilter) {
      // 같은 버튼을 또 누르면 바뀔 게 없으니 그냥 끝내요.
      if (chosenFilter === currentFilter) return;
      currentFilter = chosenFilter;

      // 1단계: 고른 버튼만 초록색(눌린 상태)으로 바꿔요.
      filterButtons.forEach(function (button) {
        button.setAttribute("aria-pressed", String(button.dataset.filter === chosenFilter));
      });

      // 2단계: 기사마다 data-keywords를 읽어서, 고른 키워드가 있으면 보이고 없으면 숨겨요.
      let visibleCount = 0;
      articleCards.forEach(function (card) {
        const keywords = card.dataset.keywords ? card.dataset.keywords.split(",") : [];
        const isVisible = chosenFilter === "all" || keywords.includes(chosenFilter);
        card.hidden = !isVisible;
        if (isVisible) visibleCount += 1;
      });

      // 3단계: 보이는 기사가 하나도 없으면 안내 문구를 보여줘요.
      emptyMessage.hidden = visibleCount > 0;
    }

    filterButtons.forEach(function (button) {
      button.addEventListener("click", function () {
        showArticles(button.dataset.filter);
      });
    });
  </script>
</body>
</html>
"""


def build_html(briefing):
    """브리핑 자료를 HTML_TEMPLATE의 빈자리에 채워서 화면(HTML) 글자로 돌려줘요."""
    # html.escape: 제목 속 < > & " 같은 글자가 화면 모양을 망가뜨리지 않게 안전한 표기로 바꿔요.
    esc = html.escape
    articles = briefing["articles"]

    # 1) 기사 칸 만들기
    article_blocks = []
    for number, article in enumerate(articles):
        keywords = article["matched_keywords"]
        if keywords:
            tags = "".join(f'<li class="tag">#{esc(k)}</li>' for k in keywords)
        else:
            tags = '<li class="tag latest">최신 기사</li>'
        # 누가 요약했는지 이름표를 하나 더 붙여요.
        if article["summary_by"] == "gemini":
            tags += '<li class="tag by">AI 요약</li>'
        else:
            tags += '<li class="tag by">소개문 발췌</li>'
        summary_lines = "".join(f"<li>{esc(line)}</li>" for line in article["summary"])
        date_text = f" · {esc(article['date'])}" if article["date"] else ""
        # 기사마다 조금씩 늦게 내려오게 해서 하나씩 쌓이는 느낌을 줘요.
        article_blocks.append(f"""          <article class="article" data-keywords="{esc(','.join(keywords))}" style="animation-delay: {number * 0.08:.2f}s">
            <h3>{esc(article['title'])}</h3>
            <ul class="tags">{tags}</ul>
            <ul class="summary">{summary_lines}</ul>
            <p class="meta">
              <span>{esc(article['source'])}{date_text}</span>
              <a class="item" href="{esc(article['link'])}" target="_blank" rel="noopener">원문 보기 ▶</a>
            </p>
          </article>""")
    if not article_blocks:
        article_blocks.append('          <p class="empty">가져온 기사가 없어요. 인터넷 연결이나 settings.json의 주소를 확인해 주세요.</p>')

    # 2) 키워드 버튼 만들기 (전체 + 키워드마다 하나씩, 옆에 기사 수)
    filter_buttons = [f'          <button type="button" class="btn" data-filter="all" aria-pressed="true">전체 <span class="count">{len(articles)}</span></button>']
    for keyword in briefing["keywords"]:
        count = sum(1 for a in articles if keyword in a["matched_keywords"])
        filter_buttons.append(
            f'          <button type="button" class="btn" data-filter="{esc(keyword)}" aria-pressed="false">#{esc(keyword)} <span class="count">{count}</span></button>'
        )

    # 3) 언론사 이름 모으기 (같은 이름은 한 번만)
    sources = list(dict.fromkeys(a["source"] for a in articles)) or ["없음"]

    # 4) 빈자리에 채워 넣기
    page = HTML_TEMPLATE
    page = page.replace("__TITLE__", esc(PAGE_TITLE))
    page = page.replace("__COLLECTED__", esc(briefing["collected_at"]))
    page = page.replace("__SOURCES__", "<br>".join(f"· {esc(s)}" for s in sources))
    page = page.replace("__FILTERS__", "\n".join(filter_buttons))
    page = page.replace("__FOOTER__", esc(FOOTER_TEXT))
    # 기사는 맨 마지막에 넣어요. (기사 글 속에 "__TITLE__" 같은 글자가 있어도 엉뚱하게 바뀌지 않게)
    page = page.replace("__ARTICLES__", "\n".join(article_blocks))
    return page


# ===== 11. 전체 순서 =====
def main():
    settings = load_settings()
    keywords = settings["keywords"]
    collected_at = datetime.now(KOREA_TIME).strftime("%Y-%m-%d %H:%M")   # 기사를 모으기 시작한 시각

    # 1단계: 모든 언론사에서 기사를 모아요. 한 곳이 안 열려도 나머지는 계속해요.
    all_articles = []
    failed_feeds = []
    for feed in settings["feeds"]:
        try:
            all_articles.extend(read_feed(feed))
        except Exception as error:
            failed_feeds.append({"source": feed["name"], "error": str(error)})

    # 2단계: 기사마다 걸린 키워드를 적어요.
    for article in all_articles:
        article["matched_keywords"] = find_keywords(article, keywords)

    # 3단계: 키워드가 걸린 기사가 몇 개인지 세어 둬요. (마지막에 알려 주려고)
    matched = [a for a in all_articles if a["matched_keywords"]]

    # 4단계: 키워드(주제)마다 돌아가며 골고루 골라서 최대 MAX_ARTICLES개를 만들어요.
    #        모자라면 키워드 없는 최신 기사로 채워요.
    picked = pick_balanced(all_articles, keywords, MAX_ARTICLES)
    # 고른 5개를 날짜 최신 순으로 다시 줄 세워요. (고를 때는 키워드 순서로 섞여 있어서)
    #  날짜가 없는 기사는 맨 뒤로 가요.
    picked.sort(key=newest_first_key)

    # 5단계: 고른 기사마다 세 줄 요약을 붙여요. (Gemini → 안 되면 소개문으로 대신)
    api_key = load_api_key()
    if not api_key:
        print("⚠️ .env에 GEMINI_API_KEY가 없어서 소개문으로 요약을 채워요.")
    add_summaries(picked, api_key)

    # 6단계: 결과 파일에 넣을 값만 골라요. (_summary, _position 같은 작업용 값은 빼요)
    briefing = {
        "collected_at": collected_at,
        "keywords": keywords,
        "articles": [
            {
                "title": a["title"],
                "link": a["link"],
                "date": a["date"],                          # 날짜가 없으면 null(값 없음)
                "source": a["source"],
                "matched_keywords": a["matched_keywords"],  # 걸린 키워드가 없으면 [] (최신 기사로 채운 것)
                "summary": a["summary"],                    # 세 줄 요약
                "summary_by": a["summary_by"],              # "gemini"(AI 요약) 또는 "rss"(소개문 발췌)
            }
            for a in picked
        ],
        "failed_feeds": failed_feeds,                       # 안 열린 언론사가 있으면 여기에 적혀요
    }

    # 7단계: news.json과 index.html로 저장해요.
    # ensure_ascii=False: 한글을 그대로 저장, indent=2: 두 칸씩 들여 써서 읽기 쉽게
    folder = Path(__file__).parent
    json_text = json.dumps(briefing, ensure_ascii=False, indent=2)
    (folder / JSON_FILE).write_text(json_text, encoding="utf-8")
    (folder / HTML_FILE).write_text(build_html(briefing), encoding="utf-8")

    print(json_text)
    print(f"\n모은 기사 {len(all_articles)}개 중 키워드 기사 {len(matched)}개")
    print(f"저장했어요: {folder / JSON_FILE}")
    print(f"저장했어요: {folder / HTML_FILE}  ← 더블클릭하면 브라우저에서 열려요")


# 이 파일을 직접 실행했을 때만 main()을 시작해요.
if __name__ == "__main__":
    main()
