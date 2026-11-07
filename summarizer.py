# ===== AI 없이 세 줄 요약 만들기 =====
# 하는 일: 기사 소개문(RSS에 들어 있는 짧은 글)에서 앞 문장 3개를 골라 "세 줄 요약"으로 돌려줘요.
#   AI처럼 새 문장을 지어내지 않고, 원래 문장을 잘라서 옮기기만 해요.
#   그래서 틀린 내용이 끼어들 일은 없지만, 문장이 길거나 덜 매끄러울 수 있어요.
# 다른 파일(briefing.py)이 이 파일의 summarize()를 빌려 써요.
# 혼자 실행해 보기:  python summarizer.py  → 예시 글로 결과를 보여줘요.
# 설치할 것은 없어요.

import re      # 글자 안에서 정해진 모양(예: "다." 로 끝나는 곳)을 찾는 도구

# ✏️ 1) 요약 줄 수: 숫자만 바꾸면 돼요
LINE_COUNT = 3
# ✏️ 2) 소개문이 없을 때 보여줄 문구: 글자만 바꾸면 돼요
NO_SUMMARY_TEXT = "소개문이 없어 요약할 수 없어요. 원문을 확인해 주세요."

# 사진 설명이 끝나는 표시예요. 경향신문 소개문은 맨 앞에 사진 설명이 붙어 있어요.
#   예: "한국예술인복지재단 제공예술 현장의..."   → "○○ 제공" 다음부터가 진짜 내용
#   예: "...2026.02.25 문재원 기자뉴욕타임스..."  → "○○○ 기자" 다음부터가 진짜 내용
# 띄어쓰기 없이 바로 다음 글자가 붙어 있는 경우만 사진 설명 끝으로 봐요.
PHOTO_CREDIT = re.compile(r"(?:^|\s)(?:\S+ 제공|[가-힣]{2,4} 기자)(?=[“‘\"'가-힣A-Za-z])")
# 사진 설명은 소개문 맨 앞쪽에만 있어서, 앞 250글자 안에서만 찾아요. (본문 속 "기자" 단어를 잘못 자르지 않게)
PHOTO_CREDIT_AREA = 250


# ===== 1. 사진 설명 떼어 내기 =====
def remove_photo_caption(text):
    """맨 앞의 사진 설명과 "○○ 제공 / ○○○ 기자" 표시를 지우고, 그 뒤 내용만 남겨요."""
    match = PHOTO_CREDIT.search(text[:PHOTO_CREDIT_AREA])
    return text[match.end():] if match else text


# ===== 2. 문장으로 나누기 =====
def split_sentences(text):
    """한국어 기사 문장은 대부분 "다."로 끝나요. 그 자리와 ? ! 뒤에서 잘라 문장 목록을 만들어요."""
    pieces = re.split(r"(?<=다\.)|(?<=[?!])\s", text)
    sentences = []
    for piece in pieces:
        piece = piece.strip()
        # 너무 짧은 조각(5글자 미만)은 문장이 아니라 부스러기라서 버려요.
        if len(piece) >= 5:
            sentences.append(piece)
    return sentences


# ===== 3. 세 줄 요약 =====
def summarize(text):
    """소개문을 받아서 요약 문장 목록(최대 LINE_COUNT개)을 돌려줘요."""
    text = (text or "").strip()
    if not text:
        return [NO_SUMMARY_TEXT]

    sentences = split_sentences(remove_photo_caption(text))

    # RSS 소개문은 끝이 "시설···"처럼 중간에 잘려 있어요.
    # 잘린 마지막 조각은 문장이 덜 끝났으니, 다른 문장이 있으면 빼요.
    complete = [s for s in sentences if not s.endswith(("···", "…", "..."))]
    lines = complete or sentences     # 다 잘린 문장뿐이면 그거라도 써요

    return lines[:LINE_COUNT] or [NO_SUMMARY_TEXT]


# ===== 4. 혼자 실행했을 때 예시 보여주기 =====
if __name__ == "__main__":
    example = ("한국예술인복지재단 제공예술 현장의 사고부터 관객 안전사고까지 보장하는 공제상품이 처음으로 출시됐다."
               "재단은 6일 첫 상품을 출시했다고 밝혔다. 예술사업자가 가입할 수 있다. 출연진과 스태프의 상해···")
    for line in summarize(example):
        print("-", line)
