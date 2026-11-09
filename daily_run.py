# ===== 하루 한 번 브리핑 실행 + 알림 =====
# 하는 일:
#   1) 오늘 이미 브리핑을 만들었는지 last_run.txt를 보고 확인해요. 만들었으면 아무것도 안 하고 끝내요.
#   2) 아직이면 briefing.py를 실행해서 news.json과 index.html을 새로 만들어요.
#   3) 기사 개수와 요약 모드(AI 요약 / 소개문 발췌)를 화면 오른쪽 아래 알림으로 짧게 알려 줘요.
# 윈도우 작업 스케줄러가 컴퓨터에 로그인할 때마다 이 파일을 실행해요.
# 직접 실행해 보기:  python daily_run.py   (오늘 이미 했어도 다시 하려면 last_run.txt를 지우세요)

# ===== 1. 필요한 도구 불러오기 =====
import contextlib                # 화면 출력을 잠깐 다른 곳으로 돌리는 도구
import io                        # 글자를 담아 두는 임시 그릇
import json
import os                        # 파일을 "더블클릭한 것처럼" 여는 도구. 브리핑 화면을 띄울 때 써요
import subprocess                # 다른 프로그램(PowerShell)을 실행하는 도구. 알림 띄울 때 써요
import traceback                 # 오류가 났을 때 자세한 내용을 글자로 만들어 주는 도구
from datetime import datetime
from pathlib import Path

FOLDER = Path(__file__).parent
LAST_RUN_FILE = FOLDER / "last_run.txt"   # 마지막으로 실행한 날짜를 적어 두는 파일
LOG_FILE = FOLDER / "daily_run.log"       # 실행 기록 (문제가 생겼을 때 원인 찾기용)
NEWS_FILE = FOLDER / "news.json"
PAGE_FILE = FOLDER / "index.html"         # 브라우저로 보는 브리핑 화면
# ✏️ 1) 알림 제목: 글자만 바꾸면 돼요
NOTICE_TITLE = "경제·IT 아침 브리핑"
# ✏️ 2) 브리핑이 끝나면 브라우저로 화면을 바로 열지: True(연다) / False(알림만)
OPEN_PAGE_AFTER_BRIEFING = True


# ===== 2. 기록 남기기 =====
def write_log(message):
    """daily_run.log 맨 아래에 '시각 + 내용' 한 줄을 덧붙여요."""
    with open(LOG_FILE, "a", encoding="utf-8") as log:
        log.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}\n")


# ===== 3. 알림 띄우기 =====
def show_notice(message):
    """화면 오른쪽 아래에 알림 풍선을 10초 동안 띄워요.
    설치 없이 쓰려고, 윈도우에 들어 있는 PowerShell의 알림 기능을 빌려 써요."""
    # 따옴표가 섞여도 PowerShell 명령이 깨지지 않게 ' 를 '' 로 바꿔요.
    title = NOTICE_TITLE.replace("'", "''")
    text = message.replace("'", "''")
    script = (
        "Add-Type -AssemblyName System.Windows.Forms;"
        "$n = New-Object System.Windows.Forms.NotifyIcon;"
        "$n.Icon = [System.Drawing.SystemIcons]::Information;"
        "$n.Visible = $true;"
        f"$n.ShowBalloonTip(10000, '{title}', '{text}', 'Info');"
        "Start-Sleep -Seconds 11;"          # 알림이 떠 있는 동안 기다렸다가
        "$n.Dispose()"                      # 아이콘을 치워요
    )
    # CREATE_NO_WINDOW: 검은 PowerShell 창이 번쩍 뜨지 않게 해요.
    subprocess.run(["powershell", "-NoProfile", "-Command", script],
                   creationflags=subprocess.CREATE_NO_WINDOW)


# ===== 4. 결과 한 줄로 줄이기 =====
def make_summary_text():
    """news.json을 읽어서 '기사 5개 · AI 요약 5개' 같은 짧은 문장을 만들어요."""
    briefing = json.loads(NEWS_FILE.read_text(encoding="utf-8"))
    articles = briefing["articles"]
    ai_count = sum(1 for a in articles if a.get("summary_by") == "gemini")
    rss_count = len(articles) - ai_count

    parts = [f"기사 {len(articles)}개"]
    if ai_count:
        parts.append(f"AI 요약 {ai_count}개")
    if rss_count:
        parts.append(f"소개문 발췌 {rss_count}개")
    if briefing.get("failed_feeds"):
        parts.append(f"안 열린 언론사 {len(briefing['failed_feeds'])}곳")
    return " · ".join(parts), len(articles)


# ===== 5. 전체 순서 =====
def main():
    today = datetime.now().strftime("%Y-%m-%d")

    # 1단계: 오늘 이미 했으면 끝내요. (하루에 딱 한 번만 실행되게)
    if LAST_RUN_FILE.exists() and LAST_RUN_FILE.read_text(encoding="utf-8").strip() == today:
        write_log("오늘은 이미 실행해서 건너뛰어요")
        return

    # 2단계: briefing.py를 실행해요. 화면 출력은 기록 파일에만 남겨요.
    #  (작업 스케줄러는 창 없이 실행해서, 출력할 화면이 없기 때문이에요)
    output = io.StringIO()
    try:
        import briefing
        with contextlib.redirect_stdout(output):
            briefing.main()
    except Exception:
        write_log("브리핑 실패:\n" + output.getvalue() + traceback.format_exc())
        show_notice("브리핑을 만들지 못했어요. daily_run.log를 확인해 주세요.")
        return    # 날짜를 적지 않아서, 다음에 켤 때 다시 시도해요

    # 3단계: 결과를 짧게 정리해서 알려 줘요.
    message, article_count = make_summary_text()
    write_log(message)

    # 4단계: 기사를 하나라도 가져왔을 때만 "오늘 했음"으로 적어요.
    #  (인터넷이 안 돼서 0개면, 다음에 켤 때 다시 시도하게)
    if article_count > 0:
        LAST_RUN_FILE.write_text(today, encoding="utf-8")
        # 5단계: 브리핑 화면(index.html)을 기본 브라우저로 열어요.
        #  알림은 오른쪽 아래에 작게 떴다 사라져서 놓치기 쉬워서, 화면을 직접 띄워 줘요.
        if OPEN_PAGE_AFTER_BRIEFING:
            try:
                os.startfile(PAGE_FILE)
                write_log("브리핑 화면을 브라우저로 열었어요")
            except OSError:
                write_log("브리핑 화면 열기 실패:\n" + traceback.format_exc())
    else:
        message += " (인터넷을 확인해 주세요. 다음에 켤 때 다시 해요)"
    show_notice(message)


if __name__ == "__main__":
    main()
