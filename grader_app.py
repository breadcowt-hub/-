import streamlit as st
import anthropic
import json
import re

# ── 페이지 설정 ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="서논술형 자동 채점",
    page_icon="📝",
    layout="wide",
)

st.markdown("""
<style>
    .main { background: #f8f9fa; }
    .stTextArea textarea { font-family: 'Malgun Gothic', sans-serif; font-size: 14px; }
    .score-box {
        background: white; border-radius: 12px; padding: 16px 20px;
        border-left: 5px solid #2C5282; margin: 8px 0;
        box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    }
    .score-pass  { border-left-color: #27AE60; background: #EAFAF1; }
    .score-partial{ border-left-color: #F39C12; background: #FEF9E7; }
    .score-fail  { border-left-color: #E74C3C; background: #FDEDEC; }
    .total-box {
        background: #1A3A5C; color: white; border-radius: 12px;
        padding: 20px; text-align: center; margin-top: 16px;
    }
    .rubric-box {
        background: #EBF2FA; border-radius: 8px; padding: 12px 16px;
        font-size: 13px; color: #2C3E50; margin: 6px 0;
    }
    h1 { color: #1A3A5C; }
    h3 { color: #2C5282; }
</style>
""", unsafe_allow_html=True)

# ── 채점 기준 (시스템 프롬프트용) ─────────────────────────────────────────
GRADING_CRITERIA = """
당신은 중학교 1학년 국어 서논술형 평가 채점 전문가입니다.
아래 채점 기준에 따라 학생 답안을 채점하고, 반드시 JSON 형식으로만 응답하세요.

## 수업 맥락
- 단원: 3. 마음이 자라는 시간 (2) 존중하며 말하기
- 학습 내용: 언어폭력의 유형(욕설/비난/비하/조롱/저주/협박), 언어의 목적(정보+감정 전달), 배려하며 말하기 3단계(나-전달법: 사실→감정→원하는 것)

---

## 문제 1 채점 기준 (각 2점 = 유형 1점 + 이유 1점)

### 핵심 원칙
- 유형 판단은 **밑줄 친 표현만** 근거로 함 (밑줄 외 부분 인용 시 이유 점수 불인정)
- 유형 용어 없이 의미가 동일하면 인정 (예: 조롱→놀림/비웃음, 비하→무시/멸시, 협박→위협, 저주→심리적 폭력)
- 유형이 틀려도 이유 서술이 올바르면 이유 1점 인정
- 오개념 방지: 다른 유형의 특성을 설명에 쓰면 이유 0점

### 1-1) 거제 발언 — 밑줄: "계룡이 너 어차피 체험학습도 맨날 혼자인 홀룡이잖아 ㅎㅎ"
- 정답 유형: 조롱
- 핵심 근거: '홀룡이'라는 별명으로 부르며 비웃는 것('ㅎㅎ') → 상대를 웃음거리로 삼는 행위
- 유형 허용: 조롱, 놀림, 비웃음
- 유형 오답: 비하(깎아내리는 평가 ≠ 놀리는 행위), 비난, 협박, 저주
- 이유 필수 요소: '홀룡이' 또는 '놀리다/비웃다/웃음거리' 언급
- 오개념 예시: "깎아내렸기 때문이다" → 비하 특성 사용, 이유 0점

### 1-2) 고현 발언 — 밑줄: "짝도 없으면서"
- 정답 유형: 비하
- 핵심 근거: '짝도 없으면서' → 계룡의 처지 자체를 낮잡아 보는 것
- 유형 허용: 비하, 무시, 멸시
- 유형 오답: 조롱(비웃는 말투 없음), 비난(행동 꾸짖음 아님)
- 이유 필수 요소: '짝도 없으면서' 인용 + 처지를 낮추거나 깎아내린다는 내용
- 밑줄 외 표현("억지로 붙여주는 거")을 근거로 쓰면 이유 0점
- 오개념 예시: "비웃었기 때문이다" → 조롱 특성 사용, 이유 0점

### 1-3) 장평 발언 — 밑줄: "버스 우리 자리 넘보지 마. 오지 말라고 가만 안 둔다."
- 정답 유형: 협박
- 핵심 근거: '가만 안 둔다' → 해를 가할 것을 암시하는 위협, 행동 강제
- 유형 허용: 협박, 위협
- 유형 오답: 비난(꾸짖음 아님), 따돌림(수업에서 배운 유형 아님)
- 이유 필수 요소: '가만 안 둔다' 인용 또는 위협·강제성 언급
- 오개념 예시: "나쁜 상황을 바랐기 때문이다" → 저주 특성, 이유 0점

### 1-4) 중곡 발언 — 밑줄: "어차피 아무도 안 반긴다."
- 정답 유형: 저주
- 핵심 근거: '아무도 안 반긴다' → 나쁜 상황을 단정하며 존재를 부정
- 유형 허용: 저주, 심리적 폭력
- 유형 오답: 비난(행동 꾸짖음 아님), 협박(강제·위협 없음)
- 이유 필수 요소: '아무도 안 반긴다' 인용 + 존재 부정/나쁜 상황 단정 언급
- '결석해라' 인용 시 밑줄 외 표현이므로 이유 0점
- 오개념 예시: "위협했기 때문이다" → 협박 특성, 이유 0점

---

## 문제 2 채점 기준

### 2-1) 세모의 의도 분석 (4점: 내용 2점 + 감정 2점)
- 내용(2점): 발표를 지켜봐 주고 관심 가져달라는 바람/부탁 → '지켜봐 주다', '관심', '봐줬으면' 등
  - 2점: 바람/부탁의 뉘앙스가 명확히 드러남
  - 1점: 내용은 맞으나 표현이 모호하거나 감정과 혼용
  - 0점: 내용 없음 또는 "화가 났다"처럼 감정으로 대체
- 감정(2점): 서운함·속상함 → '서운하다', '속상하다', '섭섭하다', '무시당한 것 같다', '상처받다' 등
  - 2점: 서운함·속상함 계열 감정이 명확히 드러남
  - 1점: '긴장했다'처럼 핵심 감정(서운함·속상함) 빠지고 주변 감정만 있음
  - 0점: 감정 없음
- 형식: "세모가 전달하려 했던 내용은 ~이다. 세모가 표현하고 싶었던 감정은 ~이다." 형식
  - 형식 미준수 시 감점 없음 (내용·감정이 구분되는지로만 채점)
- 오개념 방지: 내용과 감정을 한 문장에 합치면 내용·감정 각 1점씩만 인정

### 2-2) 메시지 불일치 비교 (8점: 의도 3점 + 실제 메시지 3점 + 차이·결과 2점)
- 의도(3점): 지켜봐 달라는 바람과 서운함
  - 3점: 바람(지켜봐 달라)과 서운함이 모두 명확
  - 2점: 둘 중 하나만 명확
  - 1점: 의도 언급은 있으나 매우 모호
- 실제 메시지(3점): 지문 표현 직접 인용 + 비난/협박 성격 언급
  - 3점: 지문 표현('맨날 딴짓', '안 도와줄 거야' 중 하나 이상) 인용 + 비난·협박 성격 서술
  - 2점: 지문 인용은 있으나 비난·협박 성격 미언급, 또는 성격은 있으나 인용 없음
  - 1점: 추상적 서술("나쁜 말을 했다") 수준
- 차이·결과(2점): 두 메시지가 달라서 진심이 전달되지 않았다는 내용
  - 2점: '전달되지 않다', '알아채지 못하다', '공격받다', '상처' 등이 드러남
  - 1점: 차이 언급은 있으나 결과·영향 없음 (2문장에서 끝내는 경우)
  - 0점: 두 메시지 나열만 하고 차이·결과 없음

---

## 문제 3 채점 기준 (10점: 1단계 3점 + 2단계 3점 + 3단계 3점 + 형식 1점)

### 핵심 맥락
- ㉠("야, 너 때문에 우리 팀 다 망하겠다. 진짜 왜 이래?")은 팀원이 한 말
- 채점 대상: 그 **팀원 입장**에서 나-전달법으로 고쳐 말하는 것
- 즉, 팀원이 실수한 계룡에게 화 대신 나-전달법으로 말하는 상황

### 1단계 — 사실 (3점)
- 핵심: 평가·감정·해석 없이 관찰한 사실만 서술
- 필수: 상대의 행동('계속 실수하다', '실수를 반복하다' 등) + 지각 동사('보았다', '들었다')
- 3점: 평가·감정 없이 사실만 서술
- 2점: 발언 인용 없이 "소리를 질렀다" 수준, 또는 경미한 평가 혼입
- 1점: 평가·비난이 섞임 ("네가 못해서", "네 실수 때문에")
- 0점: 사실 서술 없음 또는 완전히 비난 형태

### 2단계 — 감정 (3점)
- 핵심: 팀원의 감정 (불안, 초조, 걱정, 답답함 등) 2가지 이상
- 3점: 구체적 감정 단어 2가지 이상
- 2점: 감정 1가지만 있거나, '화가 났다' 1가지만 있는 경우
- 1점: '기분이 나빴다'처럼 막연한 감정 표현
- 0점: 감정 서술 없음

### 3단계 — 원하는 것 (3점)
- 핵심: 팀원이 진짜 원하는 것(상대가 집중해서 연습해 주길)을 정중하게 요청
- 3점: 구체적 대안 행동 + 정중한 요청 표현('~해 줬으면 좋겠다' 등)
- 2점: 정중하지만 추상적("사이좋게 하자"), 또는 구체적이지만 명령형("집중해")
- 1점: 2단계 감정 반복 또는 원하는 것이 매우 모호
- 0점: 3단계 내용 없음

### 형식 (1점)
- 1점: 사실→감정→원하는 것 3단계가 순서대로 모두 포함, 3문장 이내
- 0점: 3단계 중 하나라도 빠짐, 순서 역전, 3문장 초과

---

## JSON 응답 형식

반드시 아래 형식으로만 응답하세요. 다른 텍스트 절대 금지.

{
  "results": [
    {
      "id": "문항ID (예: 1-1, 1-2, 2-1, 2-2, 3)",
      "scores": {
        "항목명": {"score": 점수, "max": 최대점수, "reason": "채점 이유 1~2문장"}
      },
      "total": 합계점수,
      "max_total": 최대점수,
      "feedback": "학생에게 전달할 종합 피드백 2~3문장"
    }
  ]
}
"""

# ── 채점 함수 ──────────────────────────────────────────────────────────────
def grade_answers(answers: dict) -> dict:
    """Claude API로 채점 수행"""
    client = anthropic.Anthropic()

    # 답안 텍스트 구성
    answer_text = ""

    # 문제 1
    for i, key in enumerate(["q1_1", "q1_2", "q1_3", "q1_4"], 1):
        names = ["거제", "고현", "장평", "중곡"]
        val = answers.get(key, "").strip()
        answer_text += f"\n[문제 1-{i}] {names[i-1]}의 발언:\n{val if val else '(미응답)'}\n"

    # 문제 2
    answer_text += f"\n[문제 2-1] 세모의 의도 분석:\n{answers.get('q2_1','').strip() or '(미응답)'}\n"
    answer_text += f"\n[문제 2-2] 메시지 불일치 비교:\n{answers.get('q2_2','').strip() or '(미응답)'}\n"

    # 문제 3
    answer_text += f"\n[문제 3] 나-전달법 고쳐 말하기:\n{answers.get('q3','').strip() or '(미응답)'}\n"

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        system=GRADING_CRITERIA,
        messages=[{
            "role": "user",
            "content": f"다음 학생 답안을 채점해 주세요.\n\n{answer_text}"
        }]
    )

    raw = response.content[0].text.strip()
    # JSON 파싱
    json_match = re.search(r'\{[\s\S]*\}', raw)
    if json_match:
        return json.loads(json_match.group())
    return {"results": []}


# ── UI 헬퍼 ───────────────────────────────────────────────────────────────
def score_class(score, max_score):
    ratio = score / max_score if max_score > 0 else 0
    if ratio >= 1.0: return "score-pass"
    if ratio >= 0.5: return "score-partial"
    return "score-fail"

def score_emoji(score, max_score):
    ratio = score / max_score if max_score > 0 else 0
    if ratio >= 1.0: return "✅"
    if ratio >= 0.5: return "⚡"
    return "❌"

def render_result(result: dict):
    sid   = result["id"]
    total = result["total"]
    mxtot = result["max_total"]
    cls   = score_class(total, mxtot)
    emoji = score_emoji(total, mxtot)

    label_map = {
        "1-1": "문제 1-1  거제 발언", "1-2": "문제 1-2  고현 발언",
        "1-3": "문제 1-3  장평 발언", "1-4": "문제 1-4  중곡 발언",
        "2-1": "문제 2-1  세모의 의도 분석",
        "2-2": "문제 2-2  메시지 불일치 비교",
        "3":   "문제 3  나-전달법 고쳐 말하기",
    }
    label = label_map.get(sid, sid)

    st.markdown(f"""
    <div class="score-box {cls}">
      <b>{emoji} {label}</b>
      &nbsp;&nbsp;
      <span style="font-size:18px;font-weight:bold;">{total} / {mxtot}점</span>
    </div>
    """, unsafe_allow_html=True)

    # 세부 채점
    with st.expander("세부 채점 보기", expanded=(total < mxtot)):
        for item_name, item in result["scores"].items():
            sc, mx, reason = item["score"], item["max"], item["reason"]
            c = score_class(sc, mx)
            e = score_emoji(sc, mx)
            st.markdown(f"""
            <div class="score-box {c}" style="margin:4px 0;padding:10px 14px;">
              {e} <b>{item_name}</b>: {sc}/{mx}점
              <br><span style="font-size:13px;color:#444;">{reason}</span>
            </div>
            """, unsafe_allow_html=True)

        # 피드백
        st.markdown(f"""
        <div class="rubric-box">
          💬 <b>피드백:</b> {result.get("feedback","")}
        </div>
        """, unsafe_allow_html=True)


# ── 메인 UI ───────────────────────────────────────────────────────────────
st.title("📝 서논술형 자동 채점")
st.caption("3. 마음이 자라는 시간 ② 존중하며 말하기 | 총 30점")

# 탭 구성
tab_q, tab_ref = st.tabs(["✏️ 답안 입력 & 채점", "📋 채점 기준 참고"])

with tab_ref:
    st.markdown("### 문제 1 — 언어폭력 유형 판단 기준")
    st.markdown("""
    | 발언자 | 밑줄 표현 | 정답 유형 | 핵심 근거 |
    |--------|-----------|----------|-----------|
    | 거제 | "계룡이 너 어차피 체험학습도 맨날 혼자인 홀룡이잖아 ㅎㅎ" | **조롱** | '홀룡이' 별명 + 비웃음('ㅎㅎ') |
    | 고현 | "짝도 없으면서" | **비하** | 처지 자체를 낮잡아 봄 |
    | 장평 | "버스 우리 자리 넘보지 마. 오지 말라고 가만 안 둔다." | **협박** | '가만 안 둔다' — 위협·강제 |
    | 중곡 | "어차피 아무도 안 반긴다." | **저주** | 나쁜 상황 단정, 존재 부정 |
    """)

    st.markdown("### 유형 혼동 방지")
    cols = st.columns(3)
    with cols[0]:
        st.info("**조롱 vs 비하**\n\n조롱 = 놀리는 행위 (별명·비웃음)\n\n비하 = 깎아내리는 평가")
    with cols[1]:
        st.info("**비난 vs 협박**\n\n비난 = 잘못을 꾸짖음\n\n협박 = 해를 가하겠다는 위협")
    with cols[2]:
        st.info("**비난 vs 저주**\n\n비난 = 행동을 꾸짖음\n\n저주 = 나쁜 상황을 바람·단정")

    st.markdown("### 문제 2 배점")
    st.markdown("""
    | 소문항 | 항목 | 배점 |
    |--------|------|------|
    | 2-1 | 내용(바람) | 2점 |
    | 2-1 | 감정(서운함·속상함) | 2점 |
    | 2-2 | 의도한 메시지 | 3점 |
    | 2-2 | 실제 전달된 메시지 | 3점 |
    | 2-2 | 차이·결과 | 2점 |
    """)

    st.markdown("### 문제 3 배점")
    st.markdown("""
    | 단계 | 내용 | 배점 |
    |------|------|------|
    | 1단계 | 사실 (평가 없이 관찰한 것) | 3점 |
    | 2단계 | 감정 2가지 이상 | 3점 |
    | 3단계 | 원하는 것 (정중한 요청) | 3점 |
    | 형식 | 3단계 순서 완결, 3문장 이내 | 1점 |
    """)

with tab_q:
    st.markdown("### 문제 1  [기본형]  (8점, 각 2점)")
    st.markdown("""
    <div class="rubric-box">
    📱 <b>단톡방 「우리 반 다 모여」</b><br>
    담임쌤: 내일 체험학습 집합 장소가 바뀌었어요. 공지 꼭 확인하세요 😊<br>
    계룡: 와, 어디로요?<br>
    거제: ㅋㅋ <u>계룡이 너 어차피 체험학습도 맨날 혼자인 홀룡이잖아 ㅎㅎ</u>. 뭐가 궁금해?<br>
    고현: 맞음. <u>짝도 없으면서</u> 선생님이 억지로 붙여주는 거 아니야?<br>
    장평: 야, 계룡아. <u>버스 우리 자리 넘보지 마. 오지 말라고 가만 안 둔다.</u><br>
    중곡: 계룡아, 그냥 그날 결석해라. <u>어차피 아무도 안 반긴다.</u><br>
    계룡: ...
    </div>
    """, unsafe_allow_html=True)

    st.caption("📌 조건: 유형은 욕설/비난/비하/조롱/저주/협박 중 선택 | 형식: 'OO의 발언은 ~에 해당한다. 왜냐하면 ~이기 때문이다.'")
    st.markdown("")

    col1, col2 = st.columns(2)
    with col1:
        q1_1 = st.text_area("1) 거제의 발언 (밑줄 친 부분)", height=90, key="q1_1",
                             placeholder="거제의 발언은 ~에 해당한다. 왜냐하면 ~이기 때문이다.")
        q1_2 = st.text_area("2) 고현의 발언 (밑줄 친 부분)", height=90, key="q1_2",
                             placeholder="고현의 발언은 ~에 해당한다. 왜냐하면 ~이기 때문이다.")
    with col2:
        q1_3 = st.text_area("3) 장평의 발언 (밑줄 친 부분)", height=90, key="q1_3",
                             placeholder="장평의 발언은 ~에 해당한다. 왜냐하면 ~이기 때문이다.")
        q1_4 = st.text_area("4) 중곡의 발언 (밑줄 친 부분)", height=90, key="q1_4",
                             placeholder="중곡의 발언은 ~에 해당한다. 왜냐하면 ~이기 때문이다.")

    st.divider()
    st.markdown("### 문제 2  [심화형]  (12점)")
    st.markdown("""
    <div class="rubric-box">
    🏫 <b>교실 대화</b><br>
    발표를 마치고 자리에 돌아온 세모가 짝꿍 네모에게 낮은 목소리로 말했다.<br>
    세모: "야, 너 왜 내 발표할 때 맨날 딴짓이야? 자꾸 그러면 나도 다음부터 네 거 안 도와줄 거야."<br>
    네모는 아무 말 없이 고개를 돌렸다.<br>
    ※ 참고: 세모는 오늘 발표를 매우 긴장하며 준비했고, 네모가 지켜봐 줬으면 하는 바람이 있었다.
    </div>
    """, unsafe_allow_html=True)

    q2_1 = st.text_area(
        '1) 세모가 네모에게 진짜 전달하려 했던 내용과 감정을 각각 밝혀 서술하시오. (4점)',
        height=100, key="q2_1",
        placeholder='세모가 전달하려 했던 내용은 ~이다. 세모가 표현하고 싶었던 감정은 ~이다.')

    q2_2 = st.text_area(
        '2) 세모가 의도한 메시지와 실제로 전달된 메시지가 어떻게 다른지 비교하여 서술하시오. (8점, 3문장 이내)',
        height=130, key="q2_2",
        placeholder='세모가 의도한 메시지는 ~이었다. 그러나 실제로 전달된 메시지는 ~이었다. 그 결과 ~.')

    st.divider()
    st.markdown("### 문제 3  [심화형]  (10점)")
    st.markdown("""
    <div class="rubric-box">
    🏃 <b>상황</b><br>
    체육대회 단체 줄넘기 연습 중, 내가 계속 실수를 하자 팀원 중 한 명이<br>
    ㉠ <b>"야, 너 때문에 우리 팀 다 망하겠다. 진짜 왜 이래?"</b>라고 소리를 질렀다.
    </div>
    """, unsafe_allow_html=True)
    st.caption("📌 조건: ㉠을 말한 팀원 입장에서 나-전달법(사실→감정→원하는 것) 3단계로 고쳐 서술 | 3문장 이내")

    q3 = st.text_area(
        "1) ㉠을 배려하며 말하기 방법(나-전달법)에 맞게 고쳐 말한다면 어떻게 말할지 서술하시오.",
        height=130, key="q3",
        placeholder="나는 네가 ~ 것을 보았다. 그걸 보면서 나는 ~하고 ~했다. 앞으로 ~ 해 줬으면 좋겠다.")

    st.divider()

    # 채점 버튼
    col_btn, col_info = st.columns([1, 3])
    with col_btn:
        grade_btn = st.button("🎯 채점하기", type="primary", use_container_width=True)
    with col_info:
        st.caption("Claude AI가 채점 기준에 따라 각 문항을 자동 채점합니다.")

    if grade_btn:
        answers = {
            "q1_1": st.session_state.get("q1_1", ""),
            "q1_2": st.session_state.get("q1_2", ""),
            "q1_3": st.session_state.get("q1_3", ""),
            "q1_4": st.session_state.get("q1_4", ""),
            "q2_1": st.session_state.get("q2_1", ""),
            "q2_2": st.session_state.get("q2_2", ""),
            "q3":   st.session_state.get("q3",   ""),
        }

        # 미응답 체크
        empty = [k for k, v in answers.items() if not v.strip()]
        if len(empty) == len(answers):
            st.warning("⚠️ 답안을 하나 이상 입력해 주세요.")
        else:
            with st.spinner("채점 중입니다..."):
                try:
                    result_data = grade_answers(answers)

                    st.markdown("---")
                    st.markdown("## 📊 채점 결과")

                    grand_total = 0
                    grand_max   = 0

                    id_order = ["1-1","1-2","1-3","1-4","2-1","2-2","3"]
                    results_map = {r["id"]: r for r in result_data.get("results", [])}

                    for rid in id_order:
                        if rid in results_map:
                            r = results_map[rid]
                            render_result(r)
                            grand_total += r.get("total", 0)
                            grand_max   += r.get("max_total", 0)

                    # 총점
                    pct = int(grand_total / grand_max * 100) if grand_max else 0
                    grade_label = (
                        "🏆 우수" if pct >= 80 else
                        "👍 보통" if pct >= 50 else
                        "💪 노력 필요"
                    )
                    st.markdown(f"""
                    <div class="total-box">
                      <div style="font-size:16px;opacity:0.8;">총점</div>
                      <div style="font-size:42px;font-weight:bold;">{grand_total} / {grand_max}점</div>
                      <div style="font-size:18px;margin-top:8px;">{grade_label} ({pct}%)</div>
                    </div>
                    """, unsafe_allow_html=True)

                except json.JSONDecodeError:
                    st.error("채점 결과를 파싱하는 데 실패했습니다. 다시 시도해 주세요.")
                except Exception as e:
                    st.error(f"채점 중 오류가 발생했습니다: {e}")
