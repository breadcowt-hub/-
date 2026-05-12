import streamlit as st
import anthropic
import json
import re
import os

st.set_page_config(page_title="서논술형 자동 채점", page_icon="📝", layout="wide")

st.markdown("""
<style>
    .main { background: #f8f9fa; }
    .stTextArea textarea { font-family: 'Malgun Gothic', sans-serif; font-size: 14px; }
    .data-box {
        background: #EBF2FA; border: 2px solid #2C5282; border-radius: 10px;
        padding: 16px 20px; margin: 8px 0 12px 0;
        line-height: 1.9; font-size: 14.5px; color: #1A2A3A;
    }
    .cond-box {
        background: #F2F3F4; border: 1px solid #BBBBBB; border-radius: 8px;
        padding: 12px 16px; margin: 6px 0 10px 0;
        font-size: 14px; color: #333;
    }
    .score-box {
        background: white; border-radius: 10px; padding: 14px 18px;
        border-left: 5px solid #2C5282; margin: 6px 0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.07);
    }
    .score-pass    { border-left-color: #27AE60; background: #EAFAF1; }
    .score-partial { border-left-color: #F39C12; background: #FEF9E7; }
    .score-fail    { border-left-color: #E74C3C; background: #FDEDEC; }
    .total-box {
        background: #1A3A5C; color: white; border-radius: 12px;
        padding: 20px; text-align: center; margin-top: 16px;
    }
    .section-header {
        background: #2C5282; color: white; border-radius: 8px;
        padding: 10px 18px; font-size: 16px; font-weight: bold;
        margin: 20px 0 10px 0;
    }
    .q-text {
        font-size: 15px; font-weight: 600; color: #1A2A3A;
        margin: 14px 0 4px 0;
    }
    .review-box {
        background: #FEF9E7; border: 1.5px solid #F39C12;
        border-radius: 10px; padding: 14px 18px; margin: 10px 0;
        line-height: 1.8;
    }
    .brand-text { font-size: 15px; color: #e75480; text-align: center; margin-bottom: 2px; font-weight: bold; }
    .title-text { font-size: 28px; font-weight: bold; color: #1A3A5C; text-align: center; margin-bottom: 4px; }
    .sub-text   { font-size: 13px; color: #666; text-align: center; margin-bottom: 16px; }
    .counter-box {
        background: white; border-radius: 10px; padding: 10px 16px;
        border: 1.5px solid #2C5282; margin: 8px 0 12px 0;
        display: flex; gap: 16px; align-items: center; flex-wrap: wrap;
    }
    .counter-item { font-size: 13px; color: #444; }
    .counter-done { color: #27AE60; font-weight: bold; }
    .counter-todo { color: #AAAAAA; }
</style>
""", unsafe_allow_html=True)

# ── 채점 기준 ──────────────────────────────────────────────────────────────
GRADING_CRITERIA = """
당신은 중학교 1학년 국어 서논술형 평가 채점 전문가입니다.
아래 채점 기준에 따라 학생 답안을 채점하고, 반드시 JSON 형식으로만 응답하세요.
응답에 마크다운 기호(**, *, #), 특수 따옴표, 기타 특수기호를 절대 사용하지 마세요.

중요: 힌트와 피드백 작성 규칙
1. 정답 단어(욕설/비난/비하/조롱/저주/협박 등 유형명)를 절대 언급하지 마세요.
2. 정답을 암시하는 표현도 금지입니다. 예를 들어 "놀리는", "비웃는" 같은 조롱의 동의어도 사용 금지.
3. 대신 학생이 스스로 생각할 수 있도록 아래 방식으로만 힌트를 작성하세요.
   - 밑줄 친 표현의 어떤 부분을 다시 읽어보라고 안내하기
   - 그 표현을 들은 상대방이 어떤 감정을 느낄지 생각해보라고 유도하기
   - 말하는 사람의 의도가 무엇인지 다시 생각해보라고 안내하기
   - 수업 시간에 배운 6가지 유형의 특징을 떠올려보라고 안내하기 (유형명 언급 금지)
4. 힌트 예시:
   - 좋은 예: "가만 안 둔다는 표현이 상대에게 어떤 감정을 줄지 생각해보세요. 수업 시간에 배운 유형 중 상대를 두렵게 만드는 유형이 무엇인지 떠올려 보세요."
   - 나쁜 예: "협박에 해당합니다", "위협적인 표현이므로 협박입니다", "놀리는 행위이므로 조롱입니다"
5. 맞은 경우에는 hint를 빈 문자열로 두세요.

수업 맥락
단원: 3. 마음이 자라는 시간 (2) 존중하며 말하기
학습 내용: 언어폭력의 유형(욕설/비난/비하/조롱/저주/협박), 언어의 목적(정보+감정 전달), 배려하며 말하기 3단계(나-전달법: 사실 감정 원하는 것)

문제 1 채점 기준 (각 2점 = 유형 1점 + 이유 1점)
핵심 원칙
- 유형 판단은 밑줄 친 표현만 근거로 함 (밑줄 외 부분 인용 시 이유 점수 불인정)
- 유형 용어 없이 의미가 동일하면 인정 (조롱=놀림/비웃음, 비하=무시/멸시, 협박=위협, 저주=심리적 폭력)
- 유형이 틀려도 이유 서술이 올바르면 이유 1점 인정
- 오개념 방지: 다른 유형의 특성을 설명에 쓰면 이유 0점

1-1) 거제 발언 밑줄: 계룡이 너 어차피 체험학습도 맨날 혼자인 홀룡이잖아 ㅎㅎ
정답 유형: 조롱
핵심 근거: 홀룡이라는 별명으로 부르며 비웃는 것, 상대를 웃음거리로 삼는 행위
유형 허용: 조롱, 놀림, 비웃음
유형 오답: 비하(깎아내리는 평가는 놀리는 행위와 다름), 비난, 협박, 저주
이유 필수 요소: 홀룡이 또는 놀리다/비웃다/웃음거리 언급
오개념: 깎아내렸기 때문이다 는 비하 특성 사용이므로 이유 0점

1-2) 고현 발언 밑줄: 짝도 없으면서
정답 유형: 비하
핵심 근거: 짝도 없으면서 는 계룡의 처지 자체를 낮잡아 보는 것
유형 허용: 비하, 무시, 멸시
유형 오답: 조롱(비웃는 말투 없음), 비난(행동 꾸짖음 아님)
이유 필수 요소: 짝도 없으면서 인용 + 처지를 낮추거나 깎아내린다는 내용
밑줄 외 표현인 억지로 붙여주는 거를 근거로 쓰면 이유 0점
오개념: 비웃었기 때문이다 는 조롱 특성 사용이므로 이유 0점

1-3) 장평 발언 밑줄: 버스 우리 자리 넘보지 마. 오지 말라고 가만 안 둔다.
정답 유형: 협박
핵심 근거: 가만 안 둔다 는 해를 가할 것을 암시하는 위협과 행동 강제
유형 허용: 협박, 위협
유형 오답: 비난(꾸짖음 아님), 따돌림(수업에서 배운 유형 아님)
이유 필수 요소: 가만 안 둔다 인용 또는 위협 강제성 언급
오개념: 나쁜 상황을 바랐기 때문이다 는 저주 특성이므로 이유 0점

1-4) 중곡 발언 밑줄: 어차피 아무도 안 반긴다.
정답 유형: 저주
핵심 근거: 아무도 안 반긴다 는 나쁜 상황을 단정하며 존재를 부정
유형 허용: 저주, 심리적 폭력
유형 오답: 비난(행동 꾸짖음 아님), 협박(강제 위협 없음)
이유 필수 요소: 아무도 안 반긴다 인용 + 존재 부정/나쁜 상황 단정 언급
결석해라 인용 시 밑줄 외 표현이므로 이유 0점
오개념: 위협했기 때문이다 는 협박 특성이므로 이유 0점

문제 2 채점 기준
2-1) 세모의 의도 분석 (4점: 내용 2점 + 감정 2점)
내용(2점): 발표를 지켜봐 주고 관심 가져달라는 바람/부탁
  2점: 바람/부탁의 뉘앙스가 명확히 드러남
  1점: 내용은 맞으나 표현이 모호하거나 감정과 혼용
  0점: 내용 없음 또는 화가 났다처럼 감정으로 대체
감정(2점): 서운함 속상함 계열
  2점: 서운함 속상함 계열 감정이 명확히 드러남
  1점: 긴장했다처럼 핵심 감정이 빠지고 주변 감정만 있음
  0점: 감정 없음
형식 미준수 시 감점 없음. 내용과 감정이 구분되는지로만 채점.
오개념: 내용과 감정을 한 문장에 합치면 내용 감정 각 1점씩만 인정

2-2) 메시지 불일치 비교 (8점: 의도 4점 + 실제 메시지 4점)
핵심 원칙: 의도한 메시지와 실제 전달된 메시지를 모두 명확히 서술하면 만점.
차이나 결과를 별도 문장으로 쓰지 않아도 두 메시지가 대조되어 드러나면 인정.

의도(4점):
  4점: 지켜봐 달라는 바람과 서운함이 모두 명확히 드러남
  3점: 둘 중 하나만 명확히 드러남
  2점: 의도 언급은 있으나 모호함
  1점: 의도가 매우 불분명함
실제 메시지(4점):
  4점: 지문 표현(맨날 딴짓, 안 도와줄 거야 중 하나 이상) 직접 인용 + 비난·협박 성격 서술
  3점: 지문 인용은 있으나 비난·협박 성격 미언급, 또는 성격은 있으나 인용 없음
  2점: 추상적 서술 수준 (나쁜 말을 했다 등)
  1점: 실제 메시지가 매우 불분명하게 언급됨

문제 3 채점 기준 (10점: 1단계 3점 + 2단계 3점 + 3단계 3점 + 형식 1점)
핵심 맥락: 팀원 입장에서 나-전달법으로 고쳐 말하는 것. 팀원이 실수한 상대에게 화 대신 나-전달법으로 말하는 상황.

1단계 사실(3점): 평가 감정 해석 없이 관찰한 사실만 서술
  3점: 평가 감정 없이 사실만 서술
  2점: 경미한 평가 혼입
  1점: 평가 비난이 섞임
  0점: 사실 서술 없음 또는 완전히 비난 형태

2단계 감정(3점): 팀원의 감정(불안, 초조, 걱정, 답답함 등) 2가지 이상
  3점: 구체적 감정 단어 2가지 이상
  2점: 감정 1가지만 있는 경우
  1점: 기분이 나빴다처럼 막연한 감정 표현
  0점: 감정 서술 없음

3단계 원하는 것(3점): 팀원이 진짜 원하는 것을 정중하게 요청
  3점: 구체적 대안 행동 + 정중한 요청 표현
  2점: 정중하지만 추상적, 또는 구체적이지만 명령형
  1점: 원하는 것이 매우 모호
  0점: 3단계 내용 없음

형식(1점): 사실 감정 원하는 것 3단계가 순서대로 모두 포함, 3문장 이내
  0점: 3단계 중 하나라도 빠짐, 순서 역전, 3문장 초과

JSON 응답 형식 (다른 텍스트 절대 금지, 마크다운 기호 절대 사용 금지)
{
  "results": [
    {
      "id": "1-1",
      "scores": {
        "유형": {"score": 1, "max": 1, "hint": "틀렸을 경우에만 스스로 다시 생각해볼 수 있는 힌트 1문장. 정답 언급 금지."},
        "이유": {"score": 1, "max": 1, "hint": "틀렸을 경우에만 스스로 다시 생각해볼 수 있는 힌트 1문장. 정답 언급 금지."}
      },
      "total": 2,
      "max_total": 2,
      "feedback": "잘된 점과 부족한 점을 힌트 형식으로 2문장. 정답 직접 언급 금지. 평문으로 작성.",
      "needs_review": false,
      "review_concept": "",
      "review_point": "복습이 필요한 개념의 핵심 포인트를 힌트로. 정답 언급 금지. 평문.",
      "weak_point": "내 답안에서 부족했던 부분을 힌트로. 정답 언급 금지. 평문."
    }
  ]
}
needs_review는 total이 max_total보다 낮으면 true로 설정하세요.
점수가 만점이면 hint는 빈 문자열로 두세요.
모든 텍스트 값에 마크다운 기호를 절대 사용하지 마세요.
"""

# ── 채점 함수 (문제별 분리) ────────────────────────────────────────────────
def _call_api(answer_text: str) -> dict:
    import time
    api_key = st.secrets.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    client  = anthropic.Anthropic(api_key=api_key)
    for attempt in range(4):
        try:
            time.sleep(attempt * 3)
            response = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1500,
                system=GRADING_CRITERIA,
                messages=[{"role": "user", "content": f"다음 학생 답안을 채점해 주세요.\n\n{answer_text}"}]
            )
            raw = response.content[0].text.strip()
            json_match = re.search(r'\{[\s\S]*\}', raw)
            if json_match:
                return json.loads(json_match.group())
            return {"results": []}
        except Exception as e:
            if "429" in str(e) and attempt < 3:
                st.warning(f"요청이 많아 잠시 대기 중입니다... ({attempt+1}/3회 재시도)")
                continue
            raise
    return {"results": []}

def grade_q1(answers: dict) -> dict:
    names = ["거제", "고현", "장평", "중곡"]
    text  = ""
    for i, key in enumerate(["q1_1","q1_2","q1_3","q1_4"], 1):
        val  = answers.get(key, "").strip()
        text += f"\n[문제 1-{i}] {names[i-1]}의 발언:\n{val if val else '(미응답)'}\n"
    return _call_api(text)

def grade_q2(answers: dict) -> dict:
    text  = f"\n[문제 2-1] 세모의 의도 분석:\n{answers.get('q2_1','').strip() or '(미응답)'}\n"
    text += f"\n[문제 2-2] 메시지 불일치 비교:\n{answers.get('q2_2','').strip() or '(미응답)'}\n"
    return _call_api(text)

def grade_q3(answers: dict) -> dict:
    text = f"\n[문제 3] 나-전달법 고쳐 말하기:\n{answers.get('q3','').strip() or '(미응답)'}\n"
    return _call_api(text)

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

def render_inline_result(result: dict):
    total = result["total"]
    mxtot = result["max_total"]
    cls   = score_class(total, mxtot)
    emoji = score_emoji(total, mxtot)
    st.markdown(f"""
    <div class="score-box {cls}" style="margin-top:8px;">
      {emoji} <b>채점 결과</b> &nbsp;
      <span style="font-size:17px;font-weight:bold;">{total} / {mxtot}점</span>
    </div>
    """, unsafe_allow_html=True)
    with st.expander("세부 채점 보기", expanded=(total < mxtot)):
        for item_name, item in result["scores"].items():
            sc  = item["score"]
            mx  = item["max"]
            hint= item.get("hint", "")
            c   = score_class(sc, mx)
            e   = score_emoji(sc, mx)
            hint_html = f'<br><span style="font-size:13px;color:#555;">💡 {hint}</span>' if hint and sc < mx else ""
            st.markdown(f"""
            <div class="score-box {c}" style="margin:4px 0;padding:10px 14px;">
              {e} <b>{item_name}</b>: {sc}/{mx}점{hint_html}
            </div>
            """, unsafe_allow_html=True)
        fb = result.get("feedback", "")
        if fb:
            st.markdown(f"""
            <div style="background:#EBF2FA;border-radius:8px;padding:10px 14px;margin-top:8px;font-size:13px;color:#2C3E50;">
              💬 {fb}
            </div>
            """, unsafe_allow_html=True)

def qa_block(q_text, key, placeholder, height=90):
    st.markdown(f'<div class="q-text">{q_text}</div>', unsafe_allow_html=True)
    val = st.text_area(" ", height=height, key=key, placeholder=placeholder, label_visibility="collapsed")
    return val

# ── 세션 상태 초기화 ──────────────────────────────────────────────────────
for _k, _v in [("graded", False), ("results_map", {}), ("grand_total", 0), ("grand_max", 0)]:
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── 완료 카운트 계산 ──────────────────────────────────────────────────────
ALL_KEYS = ["q1_1","q1_2","q1_3","q1_4","q2_1","q2_2","q3"]
Q_LABELS = {
    "q1_1": "1-1)", "q1_2": "1-2)", "q1_3": "1-3)", "q1_4": "1-4)",
    "q2_1": "2-1)", "q2_2": "2-2)", "q3": "3)"
}
done_keys   = [k for k in ALL_KEYS if st.session_state.get(k, "").strip()]
done_count  = len(done_keys)
total_count = len(ALL_KEYS)

# ── 헤더 ──────────────────────────────────────────────────────────────────
st.markdown('<div class="brand-text">♥ 빵쌤과 함께하는 국어수업 ♥</div>', unsafe_allow_html=True)
st.markdown('<div class="title-text">📝 서논술형 자동 채점</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-text">3. 마음이 자라는 시간 ② 존중하며 말하기 | 총 30점</div>', unsafe_allow_html=True)

# 총점 항상 표시 (채점 전에는 0점, 채점할수록 누적)
_rm   = st.session_state.get("results_map", {})
_gt   = sum(r.get("total",0) for r in _rm.values())
_gm   = 30  # 고정 만점
_pct  = int(_gt / _gm * 100) if _gt > 0 else 0
_lbl  = ("🏆 우수" if _pct >= 80 else "👍 보통" if _pct >= 50 else "💪 노력 필요") if _gt > 0 else "아직 채점 전이에요"

# 문제별 채점 현황
_q1_done  = any(k in _rm for k in ["1-1","1-2","1-3","1-4"])
_q2_done  = any(k in _rm for k in ["2-1","2-2"])
_q3_done  = "3" in _rm
_q1_score = sum(_rm[k].get("total",0) for k in ["1-1","1-2","1-3","1-4"] if k in _rm)
_q2_score = sum(_rm[k].get("total",0) for k in ["2-1","2-2"] if k in _rm)
_q3_score = _rm["3"].get("total",0) if "3" in _rm else 0
_q1_str   = f"{_q1_score}/8점" if _q1_done else "미채점"
_q2_str   = f"{_q2_score}/12점" if _q2_done else "미채점"
_q3_str   = f"{_q3_score}/10점" if _q3_done else "미채점"

st.markdown(f"""
<div style="background:#1A3A5C;color:white;border-radius:12px;padding:14px 24px;
            margin:8px 0 4px 0;">
  <div style="text-align:center;margin-bottom:10px;">
    <span style="font-size:14px;opacity:0.8;">전체 총점</span>&nbsp;&nbsp;
    <span style="font-size:32px;font-weight:bold;">{_gt} / {_gm}점</span>&nbsp;&nbsp;
    <span style="font-size:15px;opacity:0.9;">{_lbl}{f" ({_pct}%)" if _gt > 0 else ""}</span>
  </div>
  <div style="display:flex;justify-content:center;gap:24px;font-size:13px;opacity:0.85;">
    <span>📘 문제 1: {_q1_str}</span>
    <span>📗 문제 2: {_q2_str}</span>
    <span>📙 문제 3: {_q3_str}</span>
  </div>
</div>
""", unsafe_allow_html=True)

# 완료 카운트 + 초기화 버튼
col_count, col_reset = st.columns([6, 1])
with col_count:
    items_html = ""
    for k in ALL_KEYS:
        filled = bool(st.session_state.get(k, "").strip())
        cls    = "counter-done" if filled else "counter-todo"
        symbol = "✔" if filled else "○"
        items_html += f'<span class="counter-item {cls}">{symbol} {Q_LABELS[k]}</span> &nbsp;'
    st.markdown(f"""
    <div class="counter-box">
      <span style="font-size:13px;font-weight:bold;color:#2C5282;">작성 완료 {done_count}/{total_count}</span>
      &nbsp;|&nbsp; {items_html}
    </div>
    """, unsafe_allow_html=True)
with col_reset:
    if st.button("🔄 처음부터 다시 풀기", type="secondary"):
        for k in ALL_KEYS:
            st.session_state.pop(k, None)
        st.session_state.graded      = False
        st.session_state.results_map = {}
        st.session_state.grand_total = 0
        st.session_state.grand_max   = 0
        st.rerun()

st.markdown(
    '<div style="font-size:11px;color:#aaa;text-align:right;margin-top:-8px;">'
    '모든 문제를 작성한 뒤 각 탭에서 채점하기 버튼을 눌러주세요. '
    '답안을 초기화하려면 오른쪽 버튼을 누르세요.</div>',
    unsafe_allow_html=True
)
st.markdown("---")

# ── 탭 ────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["📘 문제 1", "📗 문제 2", "📙 문제 3", "🔁 복습할 내용"])

# ════════════════════════════════════
# 탭 1 — 문제 1
# ════════════════════════════════════
with tab1:
    st.markdown('<div class="section-header">문제 1 &nbsp; 기본형 &nbsp; (8점, 각 2점)</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="data-box">
      📱 <b>단톡방 「우리 반 다 모여」</b><br><br>
      <b>담임쌤</b>: 내일 체험학습 집합 장소가 바뀌었어요. 공지 꼭 확인하세요 😊<br>
      <b>계&nbsp;&nbsp;룡</b>: 와, 어디로요?<br>
      <b>거&nbsp;&nbsp;제</b>: ㅋㅋ <u>계룡이 너 어차피 체험학습도 맨날 혼자인 홀룡이잖아 ㅎㅎ</u>. 뭐가 궁금해?<br>
      <b>고&nbsp;&nbsp;현</b>: 맞음. <u>짝도 없으면서</u> 선생님이 억지로 붙여주는 거 아니야?<br>
      <b>장&nbsp;&nbsp;평</b>: 야, 계룡아. <u>버스 우리 자리 넘보지 마. 오지 말라고 가만 안 둔다.</u><br>
      <b>중&nbsp;&nbsp;곡</b>: 계룡아, 그냥 그날 결석해라. <u>어차피 아무도 안 반긴다.</u><br>
      <b>계&nbsp;&nbsp;룡</b>: ...
    </div>
    """, unsafe_allow_html=True)
    st.markdown("""
    <div class="cond-box">
      ⚠️ <b>조건</b><br>
      ✅ 언어폭력 유형은 다음 중에서 <b>가장 적절한</b> 것을 골라 쓰시오: 욕설 / 비난 / 비하 / 조롱 / 저주 / 협박<br>
      ✅ 밑줄 친 부분만을 근거로 판단하시오.<br>
      ✅ 문장 형식: OO의 발언은 ~에 해당한다. 왜냐하면 ~이기 때문이다.
    </div>
    """, unsafe_allow_html=True)

    rm = st.session_state.results_map
    qa_block("1) 거제의 발언에서 나타나는 언어폭력의 유형과 그 이유를 두 문장으로 서술하시오.",
             "q1_1", "거제의 발언은 ~에 해당한다. 왜냐하면 ~이기 때문이다.")
    if st.session_state.graded and "1-1" in rm:
        render_inline_result(rm["1-1"])

    qa_block("2) 고현의 발언에서 나타나는 언어폭력의 유형과 그 이유를 두 문장으로 서술하시오.",
             "q1_2", "고현의 발언은 ~에 해당한다. 왜냐하면 ~이기 때문이다.")
    if st.session_state.graded and "1-2" in rm:
        render_inline_result(rm["1-2"])

    qa_block("3) 장평의 발언에서 나타나는 언어폭력의 유형과 그 이유를 두 문장으로 서술하시오.",
             "q1_3", "장평의 발언은 ~에 해당한다. 왜냐하면 ~이기 때문이다.")
    if st.session_state.graded and "1-3" in rm:
        render_inline_result(rm["1-3"])

    qa_block("4) 중곡의 발언에서 나타나는 언어폭력의 유형과 그 이유를 두 문장으로 서술하시오.",
             "q1_4", "중곡의 발언은 ~에 해당한다. 왜냐하면 ~이기 때문이다.")
    if st.session_state.graded and "1-4" in rm:
        render_inline_result(rm["1-4"])

    st.markdown("")
    if st.button("문제 1 채점하기", key="grade_q1", type="primary", use_container_width=True):
        answers = {k: st.session_state.get(k,"") for k in ALL_KEYS}
        with st.spinner("문제 1 채점 중입니다..."):
            try:
                data = grade_q1(answers)
                for r in data.get("results", []):
                    st.session_state.results_map[r["id"]] = r
                st.session_state.graded = True
                st.rerun()
            except Exception as e:
                st.error(f"채점 중 오류가 발생했습니다: {e}")

# ════════════════════════════════════
# 탭 2 — 문제 2
# ════════════════════════════════════
with tab2:
    st.markdown('<div class="section-header">문제 2 &nbsp; 심화형 &nbsp; (12점)</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="data-box">
      🏫 <b>교실 대화</b><br><br>
      발표를 마치고 자리에 돌아온 세모가 짝꿍 네모에게 낮은 목소리로 말했다.<br><br>
      <b>세모</b>: "야, 너 왜 내 발표할 때 맨날 딴짓이야? 자꾸 그러면 나도 다음부터 네 거 안 도와줄 거야."<br><br>
      네모는 아무 말 없이 고개를 돌렸다.<br><br>
      참고: 세모는 오늘 발표를 매우 긴장하며 준비했고, 네모가 지켜봐 줬으면 하는 바람이 있었다.
    </div>
    """, unsafe_allow_html=True)

    rm = st.session_state.results_map

    st.markdown("""
    <div class="cond-box">
      ⚠️ <b>조건</b><br>
      ✅ 문장 형식: "세모가 전달하려 했던 내용은 ~이다. 세모가 표현하고 싶었던 감정은 ~이다."
    </div>
    """, unsafe_allow_html=True)
    qa_block("1) 세모가 네모에게 진짜 전달하려 했던 내용과 감정을 각각 밝혀 서술하시오. (4점)",
             "q2_1", "세모가 전달하려 했던 내용은 ~이다. 세모가 표현하고 싶었던 감정은 ~이다.", height=95)
    if st.session_state.graded and "2-1" in rm:
        render_inline_result(rm["2-1"])

    st.markdown("""
    <div class="cond-box">
      ⚠️ <b>조건</b><br>
      ✅ 3문장 이내로 서술하시오.<br>
      ✅ 문장 형식: "세모가 의도한 메시지는 ~이었다. 그러나 실제로 전달된 메시지는 ~이었다."
    </div>
    """, unsafe_allow_html=True)
    qa_block("2) 세모가 의도한 메시지와 실제로 전달된 메시지가 어떻게 다른지 비교하여 서술하시오. (8점)",
             "q2_2", "세모가 의도한 메시지는 ~이었다. 그러나 실제로 전달된 메시지는 ~이었다. 그 결과 ~.", height=120)
    if st.session_state.graded and "2-2" in rm:
        render_inline_result(rm["2-2"])

    st.markdown("")
    if st.button("문제 2 채점하기", key="grade_q2", type="primary", use_container_width=True):
        answers = {k: st.session_state.get(k,"") for k in ALL_KEYS}
        with st.spinner("문제 2 채점 중입니다..."):
            try:
                data = grade_q2(answers)
                for r in data.get("results", []):
                    st.session_state.results_map[r["id"]] = r
                st.session_state.graded = True
                st.rerun()
            except Exception as e:
                st.error(f"채점 중 오류가 발생했습니다: {e}")

# ════════════════════════════════════
# 탭 3 — 문제 3
# ════════════════════════════════════
with tab3:
    st.markdown('<div class="section-header">문제 3 &nbsp; 심화형 &nbsp; (10점)</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="data-box">
      🏃 <b>상황</b><br><br>
      체육대회 단체 줄넘기 연습 중, 내가 계속 실수를 하자 팀원 중 한 명이<br>
      ㉠ "야, 너 때문에 우리 팀 다 망하겠다. 진짜 왜 이래?"라고 소리를 질렀다.
    </div>
    """, unsafe_allow_html=True)
    st.markdown("""
    <div class="cond-box">
      ⚠️ <b>조건</b><br>
      ✅ ㉠을 말한 팀원 입장에서 나-전달법으로 고쳐 말하는 상황으로 서술하시오.<br>
      ✅ 배려하며 말하기 3단계(사실 → 감정 → 원하는 것)가 모두 드러나야 합니다.<br>
      ✅ 3문장 이내로 서술하시오.
    </div>
    """, unsafe_allow_html=True)

    rm = st.session_state.results_map
    qa_block("1) 다음 상황에서 ㉠을 배려하며 말하기 방법(나-전달법)에 맞게 고쳐 말한다면 어떻게 말할지 서술하시오.",
             "q3", "나는 네가 ~ 것을 보았다. 그걸 보면서 나는 ~하고 ~했다. 앞으로 ~ 해 줬으면 좋겠다.", height=120)
    if st.session_state.graded and "3" in rm:
        render_inline_result(rm["3"])

    st.markdown("")
    if st.button("문제 3 채점하기", key="grade_q3", type="primary", use_container_width=True):
        answers = {k: st.session_state.get(k,"") for k in ALL_KEYS}
        with st.spinner("문제 3 채점 중입니다..."):
            try:
                data = grade_q3(answers)
                for r in data.get("results", []):
                    st.session_state.results_map[r["id"]] = r
                st.session_state.graded = True
                st.rerun()
            except Exception as e:
                st.error(f"채점 중 오류가 발생했습니다: {e}")

    # 총점을 results_map 전체 기준으로 계산
    if st.session_state.graded and st.session_state.results_map:
        gt = sum(r.get("total",0) for r in st.session_state.results_map.values())
        gm = sum(r.get("max_total",0) for r in st.session_state.results_map.values())
    if st.session_state.graded and st.session_state.results_map:
        gt  = sum(r.get("total",0) for r in st.session_state.results_map.values())
        gm  = sum(r.get("max_total",0) for r in st.session_state.results_map.values())
        pct = int(gt / gm * 100)
        grade_label = "🏆 우수" if pct >= 80 else "👍 보통" if pct >= 50 else "💪 노력 필요"
        st.markdown(f"""
        <div class="total-box">
          <div style="font-size:14px;opacity:0.8;">총점</div>
          <div style="font-size:38px;font-weight:bold;">{gt} / {gm}점</div>
          <div style="font-size:16px;margin-top:6px;">{grade_label} ({pct}%)</div>
        </div>
        """, unsafe_allow_html=True)

# ════════════════════════════════════
# 탭 4 — 복습할 내용
# ════════════════════════════════════
with tab4:
    st.markdown("### 🔁 복습할 내용")
    if not st.session_state.graded or not st.session_state.results_map:
        st.info("채점을 완료하면 여기에 복습이 필요한 내용이 표시돼요.")
    else:
        label_map = {
            "1-1": "문제 1-1  거제 발언",
            "1-2": "문제 1-2  고현 발언",
            "1-3": "문제 1-3  장평 발언",
            "1-4": "문제 1-4  중곡 발언",
            "2-1": "문제 2-1  세모의 의도 분석",
            "2-2": "문제 2-2  메시지 불일치 비교",
            "3":   "문제 3  나-전달법",
        }
        review_items = [r for r in st.session_state.results_map.values() if r.get("needs_review", False)]
        if not review_items:
            st.success("모든 문항의 조건을 충족했어요! 정말 잘했어요 🎉")
        else:
            st.markdown(f"조건을 충족하지 못한 문항이 {len(review_items)}개 있어요. 아래 힌트를 보고 다시 한 번 생각해 보세요!")
            st.markdown("")
            for r in review_items:
                label        = label_map.get(r["id"], r["id"])
                concept      = r.get("review_concept", "")
                review_point = r.get("review_point", "")
                weak_point   = r.get("weak_point", "")
                concept_line = f"<br>복습 개념: {concept}" if concept else ""
                review_line  = f"<br>💡 핵심 힌트: {review_point}" if review_point else ""
                weak_line    = f"<br>🔍 내 답안 돌아보기: {weak_point}" if weak_point else ""
                st.markdown(f"""
                <div class="review-box">
                  <b>📌 {label}</b>
                  {concept_line}{review_line}{weak_line}
                </div>
                """, unsafe_allow_html=True)
