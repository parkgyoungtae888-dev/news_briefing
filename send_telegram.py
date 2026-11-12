# ===== 브리핑 결과를 텔레그램으로 보내기 =====
# 하는 일: briefing.py가 만든 news.json을 읽어서, 기사 제목·링크·세 줄 요약을
#          텔레그램 봇으로 내 채팅방에 보내요.
# 실행 방법: briefing.py를 먼저 실행한 뒤  python send_telegram.py
#
# 준비물: 봇 토큰(봇을 움직이는 열쇠)과 채팅 번호(받을 사람 번호) 두 가지.
#   - GitHub에서는: 저장소 Settings → Secrets and variables → Actions 에
#       TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID 두 비밀값을 넣어 두면 돼요.
#   - 내 컴퓨터에서는: 같은 이름으로 환경 변수에 넣어서 실행해요.
#   토큰은 이 파일이나 저장소에 절대 직접 적지 않아요.

import html                      # 기사 제목의 < > & 글자가 메시지를 깨뜨리지 않게 바꿔 주는 도구
import json
import os                        # 환경 변수(컴퓨터가 들고 있는 설정값)를 읽는 도구
import sys
import urllib.parse
import urllib.request
from pathlib import Path

# ✏️ 1) 메시지 맨 위 제목: 글자만 바꾸면 돼요
MESSAGE_TITLE = "📰 경제·IT 아침 브리핑"
# ✏️ 2) 메시지 맨 아래 안내 문구 (웹 페이지 주소를 바꾸면 여기도 바꿔 주세요)
FOOTER_TEXT = "AI 요약은 틀릴 수 있어요. 전체 화면: https://newsbriefing-two.vercel.app/"

NEWS_FILE = Path(__file__).parent / "news.json"


# ===== 1. 메시지 모양 만들기 =====
def build_message(briefing):
    """기사마다 '번호. 제목(누르면 원문) / 언론사·시간·키워드 / 세 줄 요약' 모양으로 만들어요."""
    lines = [f"<b>{MESSAGE_TITLE}</b>", f"{briefing['collected_at']} 기준", ""]
    for number, article in enumerate(briefing["articles"], start=1):
        title = html.escape(article["title"])
        link = html.escape(article["link"], quote=True)
        lines.append(f'<b>{number}. <a href="{link}">{title}</a></b>')

        info = article["source"]
        if article.get("date"):
            info += f" · {article['date']}"
        if article.get("matched_keywords"):
            info += " · #" + " #".join(article["matched_keywords"])
        lines.append(f"<i>{html.escape(info)}</i>")

        for sentence in article["summary"]:
            lines.append(f"• {html.escape(sentence)}")
        lines.append("")
    lines.append(f"<i>{html.escape(FOOTER_TEXT)}</i>")
    return "\n".join(lines)


# ===== 2. 텔레그램으로 보내기 =====
def send(text, token, chat_id):
    """텔레그램 서버에 '이 채팅방에 이 글 보내줘' 하고 요청해요. 성공하면 True."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",                # <b>굵게</b>, <a>링크</a>를 쓰겠다는 뜻
        "disable_web_page_preview": "true",   # 링크 미리보기 카드가 크게 붙지 않게
    }).encode("utf-8")
    with urllib.request.urlopen(url, data=data, timeout=15) as response:
        return json.loads(response.read().decode("utf-8")).get("ok", False)


# ===== 3. 전체 순서 =====
def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("❌ TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID가 없어요. 비밀값(Secrets)을 확인해 주세요.")
        sys.exit(1)

    briefing = json.loads(NEWS_FILE.read_text(encoding="utf-8"))
    if send(build_message(briefing), token, chat_id):
        print(f"✅ 텔레그램으로 기사 {len(briefing['articles'])}개를 보냈어요")
    else:
        print("❌ 텔레그램 보내기 실패")
        sys.exit(1)


if __name__ == "__main__":
    main()
