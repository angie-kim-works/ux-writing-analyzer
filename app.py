import io
import re
import csv
import time
from collections import Counter

import requests
import streamlit as st

# ── 페이지 설정 ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="UX 라이팅 문체 분석기",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── 전역 스타일 ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600&display=swap');

html, body, [class*="css"] { font-family: 'Noto Sans KR', sans-serif; }

/* 메트릭 카드 */
[data-testid="metric-container"] {
    background: #f5f5f3;
    border-radius: 10px;
    padding: 14px 18px;
    border: none;
}
[data-testid="metric-container"] label { font-size: 12px !important; color: #888 !important; }
[data-testid="metric-container"] [data-testid="metric-value"] { font-size: 28px !important; font-weight: 600 !important; }

/* 배지 공통 */
.badge {
    display: inline-block;
    padding: 2px 9px;
    border-radius: 99px;
    font-size: 12px;
    font-weight: 500;
    margin-right: 4px;
}
.badge-blue   { background: #E6F1FB; color: #185FA5; }
.badge-green  { background: #E1F5EE; color: #0F6E56; }
.badge-amber  { background: #FAEEDA; color: #BA7517; }
.badge-gray   { background: #F1EFE8; color: #888780; }

/* 문장 카드 */
.s-card {
    background: #fff;
    border: 0.5px solid rgba(0,0,0,0.12);
    border-radius: 12px;
    padding: 12px 16px;
    margin-bottom: 8px;
}
.s-meta { display: flex; justify-content: space-between; align-items: flex-start;
          flex-wrap: wrap; gap: 4px; margin-bottom: 6px; }
.s-text { font-size: 14px; line-height: 1.65; margin-bottom: 7px; }
.s-detail { font-size: 12px; color: #888; }

/* 칩 그리드 */
.chip-grid { display: flex; flex-wrap: wrap; gap: 6px; }
.chip {
    display: flex; align-items: center; gap: 4px;
    background: #f5f5f3; border-radius: 8px; padding: 4px 10px; font-size: 13px;
}
.chip-cnt {
    font-size: 11px; font-weight: 600;
    background: #E6F1FB; color: #185FA5;
    border-radius: 99px; padding: 1px 6px; min-width: 18px; text-align: center;
}

/* 진행 바 레이블 */
.bar-label {
    display: flex; justify-content: space-between;
    font-size: 13px; margin-bottom: 3px;
}
.bar-sub { font-size: 12px; color: #888; }

/* 섹션 헤더 */
.section-note {
    background: #f5f5f3; border-radius: 8px; padding: 10px 14px;
    font-size: 12px; color: #888; line-height: 1.7; margin-bottom: 16px;
}
</style>
""", unsafe_allow_html=True)


# ── MeCab 초기화 (캐시) ───────────────────────────────────────────────────────
@st.cache_resource(show_spinner="MeCab 초기화 중…")
def get_mecab():
    import mecab
    return mecab.MeCab()


# ── 한자어 판별 데이터 ────────────────────────────────────────────────────────
FINANCIAL_SINO = {
    '계좌','잔액','송금','이체','완료','처리','확인','거래','결제','입금','출금','납부',
    '조회','신청','등록','변경','해지','취소','신고','접수','발급','재발급','분실',
    '도난','비밀번호','인증','승인','한도','이율','이자','수수료','면제','감면','할인',
    '적립','소비','청구','명세서','내역','현황','상태','정보','서비스','상품',
    '계약','약관','동의','철회','반환','환급','보상','손실','수익','자산','부채',
    '예금','적금','대출','상환','연체','담보','보증','보험','연금','투자','펀드',
    '주식','채권','환율','금리','기간','만기','갱신','해외','국내','통화','원화',
    '외환','환전','수령','배송','발송','도착','수신','발신','통지','안내','공지',
    '알림','경고','제한','정지','중단','재개','복구','오류','장애','점검','관리',
    '고객','회원','개인','법인','사업자','대표','대리','위임','수임','문의','상담',
    '지원','해결','신규','기존','추가','삭제','수정','조정','설정','초기화','연결',
    '연동','통합','분리','이관','전환','전달','제출','제공','요청','답변','회신',
    '응답','결과','내용','사항','조건','기준','규정','법령','시행','적용','해당',
    '관련','필요','확정','임시','최종','최초','최대','최소','불가','가능','부족',
    '초과','미만','이상','이하','동일','상이','유효','만료','연장','단축','증가',
    '감소','인상','인하','해제','이전','이후','당일','익일','영업일','본인','타인',
    '수익자','피보험자','보험료','보험금','청약','심사','인수','거절','면책','지급',
    '결정','기준일','적용일','만료일','시작일','종료일','원금','복리','단리','누적',
    '잔존','잔여','잔금','선납','후납','분납','일괄','정기','비정기','자동','수동',
    '전자','모바일','디지털','온라인','오프라인','비대면','대면','창구','지점',
    '영업점','본점','지사','콜센터','고객센터','약정','협약','체결','해약','이동',
    '이월','이연','공제','차감','가산','합산','총액','명의','대행','수탁',
    '공시','공고','고지','고시','발표',
}
FINANCIAL_COMPANIES = {
    '삼성증권','미래에셋증권','KB증권','키움증권','한국투자증권','신한투자증권',
    '하나증권','대신증권','NH투자증권','메리츠증권','교보증권','카카오페이증권','토스증권',
    'KB국민은행','신한은행','하나은행','우리은행','NH농협은행','IBK기업은행',
    '케이뱅크','카카오뱅크','토스뱅크','수협은행','SC제일은행',
    '삼성카드','현대카드','KB국민카드','신한카드','롯데카드','우리카드','하나카드','BC카드',
}
NATIVE_MARKERS = {'람','늘','울','봄','꽃','잎','별','땅','불','바람'}
HAPSHO = ('습니다','습니까','십시오','읍니다','읍니까')
HAEYO  = ('어요','아요','해요','세요','게요','네요','죠','여요','래요')
HAPSHO_EXACT = {'합니다','됩니다','있습니다','없습니다','합니까','됩니까'}

SPEECH_COLOR = {'합쇼체':'#185FA5','해요체':'#0F6E56','혼용':'#BA7517','없음':'#888780'}
SPEECH_BG    = {'합쇼체':'#E6F1FB','해요체':'#E1F5EE','혼용':'#FAEEDA','없음':'#F1EFE8'}
SPEECH_CLASS = {'합쇼체':'badge-blue','해요체':'badge-green','혼용':'badge-amber','없음':'badge-gray'}


# ── 분석 함수 ─────────────────────────────────────────────────────────────────
def is_hangul(c): return '\uAC00' <= c <= '\uD7A3'
def get_onset(c): return (ord(c) - 0xAC00) // (21 * 28)

def is_sino(word, pos):
    if pos not in ('NNG', 'NNP'): return False
    if word in FINANCIAL_COMPANIES: return False
    if word in FINANCIAL_SINO: return True
    if is_hangul(word[0]) and get_onset(word[0]) == 5: return True
    if len(word) >= 2 and pos == 'NNG' and all(is_hangul(c) for c in word):
        if not any(c in NATIVE_MARKERS for c in word): return True
    return False

def speech_level(endings):
    lvls = set()
    for e in endings:
        if e in HAPSHO_EXACT or any(e.endswith(p) for p in HAPSHO):
            lvls.add('합쇼체')
        elif any(e.endswith(p) for p in HAEYO):
            lvls.add('해요체')
    if len(lvls) >= 2: return '혼용'
    return lvls.pop() if lvls else '없음'

def analyze_sentence(sentence: str, m) -> dict:
    morphs = m.parse(sentence)
    sino, endings, hons = [], [], []
    for mo in morphs:
        w, pos = mo.surface, mo.feature.pos
        if is_sino(w, pos): sino.append(w)
        if 'EF' in pos or pos in ('XSV+EF', 'VX+EF'): endings.append(w)
        if pos == 'EP' and w in ('시', '셨'): hons.append(w)
        elif 'EP' in pos and ('시' in w or '셨' in w): hons.append(w)
    hons = list(dict.fromkeys(hons))
    return {
        'sino_words':          list(dict.fromkeys(sino)),
        'sino_count':          len(set(sino)),
        'final_endings':       endings,
        'speech_level':        speech_level(endings),
        'honorific_morphemes': hons,
        'honorific_count':     len(hons),
    }


# ── CSV 불러오기 ──────────────────────────────────────────────────────────────
def extract_id(url: str) -> str:
    m = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
    return m.group(1) if m else url.strip()

@st.cache_data(show_spinner=False)
def load_sheet(url: str) -> list[dict]:
    sid = extract_id(url)
    csv_url = f"https://docs.google.com/spreadsheets/d/{sid}/export?format=csv"
    resp = requests.get(csv_url, timeout=15)
    resp.raise_for_status()
    resp.encoding = 'utf-8'
    rows = list(csv.DictReader(io.StringIO(resp.text)))
    return [r for r in rows if any(v.strip() for v in r.values())]

def find_col(keys, candidates):
    for c in candidates:
        f = next((k for k in keys if c.lower() in k.lower()), None)
        if f: return f
    return keys[0] if keys else ''


# ── UI 헬퍼 ──────────────────────────────────────────────────────────────────
def badge(label, cls='badge-gray'):
    return f'<span class="badge {cls}">{label}</span>'

def progress_bar(val, mx, color, height=7):
    p = round(val / mx * 100) if mx else 0
    return f"""
    <div style="display:flex;align-items:center;gap:8px;margin-top:4px">
      <div style="flex:1;height:{height}px;background:#eee;border-radius:4px;overflow:hidden">
        <div style="width:{p}%;height:100%;background:{color};border-radius:4px;transition:width .4s"></div>
      </div>
      <span style="font-size:11px;color:#aaa;min-width:34px;text-align:right">{p}%</span>
    </div>"""

def pct(v, t): return round(v / t * 100) if t else 0


# ── 메인 앱 ──────────────────────────────────────────────────────────────────
def main():
    # ── 헤더
    st.markdown("## UX 라이팅 문체 분석기")
    st.caption("MeCab-ko 형태소 분석 기반  ·  Google 스프레드시트 연동")
    st.divider()

    # ── URL 입력
    col_input, col_btn = st.columns([5, 1])
    with col_input:
        sheet_url = st.text_input(
            label="스프레드시트 URL",
            placeholder="URL 입력",
            label_visibility="collapsed",
        )
    with col_btn:
        load_clicked = st.button("불러오기", use_container_width=True, type="primary")
    st.caption("스프레드시트 공유 설정을 **'링크가 있는 모든 사용자'** 로 설정 후 공유")

    # ── 데이터 로드
    if load_clicked and sheet_url:
        st.session_state.pop("results", None)   # 이전 결과 초기화
        with st.spinner("스프레드시트 불러오는 중…"):
            try:
                load_sheet.clear()
                rows = load_sheet(sheet_url)
                st.session_state["rows"] = rows
                st.session_state["sheet_url"] = sheet_url
                st.success(f"✓ {len(rows)}개 문장 로드 완료")
            except requests.HTTPError as e:
                st.error(f"불러오기 실패: HTTP {e.response.status_code} — 공유 설정을 확인하세요.")
                return
            except Exception as e:
                st.error(f"불러오기 실패: {e}")
                return

    rows = st.session_state.get("rows", [])
    if not rows:
        st.info("스프레드시트 URL을 입력하고 불러오기를 눌러주세요.")
        return

    keys     = list(rows[0].keys())
    sent_key = find_col(keys, ['문장','sentence','text'])
    type_key = find_col(keys, ['유형','type','category'])
    proc_key = find_col(keys, ['프로세스','process','flow'])

    # ── 분석 실행
    if "results" not in st.session_state:
        m = get_mecab()
        results = []
        prog = st.progress(0, text="형태소 분석 중…")
        total = len(rows)
        for i, row in enumerate(rows):
            sent = row.get(sent_key, '').strip()
            results.append({
                '_sentence': sent,
                '_type':     row.get(type_key, '').strip(),
                '_process':  row.get(proc_key, '').strip(),
                '_analysis': analyze_sentence(sent, m) if sent else None,
            })
            prog.progress((i + 1) / total, text=f"형태소 분석 중… {i+1}/{total}")
        prog.empty()
        st.session_state["results"] = results
        st.success(f"✓ 분석 완료: {total}개 문장")

    results  = st.session_state["results"]
    analyzed = [r for r in results if r['_analysis']]

    # ── 필터
    st.divider()
    f_col1, f_col2, f_col3 = st.columns([2, 2, 3])
    with f_col1:
        types = ["전체"] + sorted(set(r['_type'] for r in analyzed if r['_type']))
        sel_type = st.selectbox("유형", types, label_visibility="collapsed")
    with f_col2:
        procs = ["전체"] + sorted(set(r['_process'] for r in analyzed if r['_process']))
        sel_proc = st.selectbox("프로세스", procs, label_visibility="collapsed")
    with f_col3:
        st.caption(f"유형: {sel_type}  ·  프로세스: {sel_proc}")

    filtered = [r for r in analyzed
                if (sel_type == "전체" or r['_type'] == sel_type)
                and (sel_proc == "전체" or r['_process'] == sel_proc)]

    # ── 집계
    n             = len(filtered)
    all_sino      = [w for r in filtered for w in r['_analysis']['sino_words']]
    all_endings   = [e for r in filtered for e in r['_analysis']['final_endings']]
    all_hon       = [h for r in filtered for h in r['_analysis']['honorific_morphemes']]
    avg_sino      = round(len(all_sino) / n, 2) if n else 0
    hon_sents     = sum(1 for r in filtered if r['_analysis']['honorific_count'] > 0)
    speech_counts = Counter(r['_analysis']['speech_level'] for r in filtered)
    type_counts   = Counter(r['_type'] for r in analyzed if r['_type'])
    proc_counts   = Counter(r['_process'] for r in analyzed if r['_process'])
    sino_top      = Counter(all_sino).most_common(20)
    ending_top    = Counter(all_endings).most_common(12)
    hon_top       = Counter(all_hon).most_common(5)

    # ── 탭
    tab1, tab2, tab3, tab4 = st.tabs(["📊 전체 요약", "📂 유형 / 프로세스", "🔢 빈도 분석", "📝 문장별 결과"])

    # ── 탭1: 전체 요약 ────────────────────────────────────────────────────────
    with tab1:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("분석 문장 수",     f"{n}개")
        c2.metric("문장당 평균 한자어", f"{avg_sino}개")
        c3.metric("높임 선어말어미",   f"{len(all_hon)}회")
        c4.metric("종결어미 총계",     f"{len(all_endings)}회")

        st.markdown("#### 문체 수준 분포")
        for lvl, cnt in speech_counts.most_common():
            col_a, col_b = st.columns([1, 6])
            with col_a:
                st.markdown(
                    badge(lvl, SPEECH_CLASS.get(lvl, 'badge-gray')),
                    unsafe_allow_html=True,
                )
            with col_b:
                st.progress(pct(cnt, n) / 100, text=f"{cnt}문장  ({pct(cnt,n)}%)")

        st.markdown("#### 높임 선어말어미 사용률")
        st.caption(f"높임 표현('시/셨')이 포함된 문장: {hon_sents}개 ({pct(hon_sents, n)}%)")
        st.progress(pct(hon_sents, n) / 100)

    # ── 탭2: 유형 / 프로세스 ─────────────────────────────────────────────────
    with tab2:
        st.markdown(
            f'<div class="section-note">전체 수집 데이터 <strong>{len(results)}개</strong> 기준 유형·프로세스별 빈도</div>',
            unsafe_allow_html=True,
        )
        col_t, col_p = st.columns(2)

        with col_t:
            st.markdown("**유형별 분포**")
            if type_counts:
                for t, cnt in type_counts.most_common():
                    st.markdown(
                        f'<div class="bar-label"><span>{t}</span>'
                        f'<span class="bar-sub">{cnt}개 ({pct(cnt, len(analyzed))}%)</span></div>'
                        + progress_bar(cnt, len(analyzed), '#185FA5'),
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("유형 데이터 없음")

        with col_p:
            st.markdown("**프로세스별 분포**")
            if proc_counts:
                for p_, cnt in proc_counts.most_common():
                    st.markdown(
                        f'<div class="bar-label"><span>{p_}</span>'
                        f'<span class="bar-sub">{cnt}개 ({pct(cnt, len(analyzed))}%)</span></div>'
                        + progress_bar(cnt, len(analyzed), '#0F6E56'),
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("프로세스 데이터 없음")

    # ── 탭3: 빈도 분석 ───────────────────────────────────────────────────────
    with tab3:
        st.markdown("**상위 한자어**")
        st.caption(f"총 {len(all_sino)}회 출현  ·  {len(set(all_sino))}종")
        if sino_top:
            chips_html = '<div class="chip-grid">' + ''.join(
                f'<div class="chip"><span>{w}</span><span class="chip-cnt">{c}</span></div>'
                for w, c in sino_top
            ) + '</div>'
            st.markdown(chips_html, unsafe_allow_html=True)
        st.divider()

        col_ef, col_hon = st.columns(2)
        with col_ef:
            st.markdown("**종결어미 빈도**")
            st.caption(f"총 {len(all_endings)}회")
            max_ef = ending_top[0][1] if ending_top else 1
            for e, c in ending_top:
                st.markdown(
                    f'<div class="bar-label"><span>~{e}</span><span class="bar-sub">{c}회</span></div>'
                    + progress_bar(c, max_ef, '#BA7517'),
                    unsafe_allow_html=True,
                )

        with col_hon:
            st.markdown("**높임 선어말어미 빈도**")
            st.caption(f"총 {len(all_hon)}회")
            max_hon = hon_top[0][1] if hon_top else 1
            if hon_top:
                for h, c in hon_top:
                    st.markdown(
                        f'<div class="bar-label"><span>\'{h}\'</span><span class="bar-sub">{c}회</span></div>'
                        + progress_bar(c, max_hon, '#0F6E56'),
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("높임 선어말어미 없음")

    # ── 탭4: 문장별 결과 ─────────────────────────────────────────────────────
    with tab4:
        st.caption(f"{len(filtered)}개 문장")
        for r in filtered:
            a  = r['_analysis']
            sl = a['speech_level']
            sc = SPEECH_COLOR.get(sl, '#888')
            sb = SPEECH_BG.get(sl, '#eee')

            type_b = badge(r['_type'], 'badge-blue')   if r['_type']    else ''
            proc_b = badge(r['_process'], 'badge-green') if r['_process'] else ''
            sl_b   = f'<span class="badge" style="background:{sb};color:{sc}">{sl}</span>'

            sino_t  = f'한자어 {a["sino_count"]}개' + (': ' + ', '.join(a['sino_words'][:5]) if a['sino_words'] else '')
            ef_t    = '종결어미: ' + (', '.join(a['final_endings']) if a['final_endings'] else '없음')
            hon_t   = ('높임어미: ' + ', '.join(a['honorific_morphemes'])) if a['honorific_count'] > 0 else ''
            detail  = '  ·  '.join(x for x in [sino_t, ef_t, hon_t] if x)

            st.markdown(f"""
            <div class="s-card">
              <div class="s-meta">
                <div>{type_b}{proc_b}</div>
                {sl_b}
              </div>
              <div class="s-text">{r['_sentence']}</div>
              <div class="s-detail">{detail}</div>
            </div>""", unsafe_allow_html=True)

        st.divider()

        # CSV 내보내기
        if filtered:
            rows_export = []
            for r in filtered:
                a = r['_analysis']
                rows_export.append({
                    '유형': r['_type'], '프로세스': r['_process'], '문장': r['_sentence'],
                    '문체수준': a['speech_level'], '한자어수': a['sino_count'],
                    '한자어목록': ' / '.join(a['sino_words']),
                    '종결어미': ' / '.join(a['final_endings']),
                    '높임선어말어미수': a['honorific_count'],
                    '높임선어말어미': ' / '.join(a['honorific_morphemes']),
                })
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=rows_export[0].keys())
            writer.writeheader()
            writer.writerows(rows_export)
            st.download_button(
                label="📥 결과 CSV 다운로드",
                data=buf.getvalue().encode('utf-8-sig'),
                file_name="ux_analysis_result.csv",
                mime="text/csv",
            )


if __name__ == "__main__":
    main()
