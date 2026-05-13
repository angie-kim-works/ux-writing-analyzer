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


# ── 사용자 사전 컴파일 및 MeCab 초기화 (캐시) ────────────────────────────────
def _build_user_dic() -> str:
    """금융사명 사용자 사전을 컴파일하고 .dic 경로를 반환합니다."""
    import _mecab, mecab_ko_dic, os, tempfile

    DIC_PATH = str(mecab_ko_dic.dictionary_path)

    # 금융사명 목록 — 여기에 추가/수정하세요
    COMPANIES = [
        # 증권
        '미래에셋증권','한국투자증권','신한투자증권','카카오페이증권',
        '이베스트투자증권','NH투자증권','KB증권','하나증권','대신증권',
        '메리츠증권','교보증권','유안타증권','현대차증권','신영증권','토스증권',
        '삼성증권','우리투자증권','키움증권',
        # 은행
        'KB국민은행','NH농협은행','IBK기업은행','케이뱅크','카카오뱅크','토스뱅크',
        '수협은행','SC제일은행','씨티은행','광주은행','전북은행','경남은행',
        '부산은행','대구은행','제주은행','국민은행','하나은행','우리은행',
        '농협은행','im뱅크',
        # 카드
        'KB국민카드','NH농협카드','롯데카드','우리카드','하나카드','씨티카드',
        '현대카드','신한카드','BC카드','카카오뱅크카드','삼성카드',
    ]

   # ── NNG 일반명사 사용자 사전 ──────────────────────────────────────────
    # 단어만 추가하면 됩니다. 시스템 사전보다 무조건 우선 적용됩니다.
    NNG_TERMS = [
        '비대면', '영업점', '거래'
    ]

    def has_jongseong(char):
        if not ('\uAC00' <= char <= '\uD7A3'):
            return True  # 비한글(영문 등)은 T 처리
        return (ord(char) - 0xAC00) % 28 != 0
    
    csv_lines = []

    # NNP 고유명사 (브랜드명)
    for company in COMPANIES:
        last = company[-1]
        jong = 'T' if has_jongseong(last) else 'F'
        rid  = 3546 if jong == 'T' else 3545
        csv_lines.append(f"{company},1786,{rid},-5000,NNP,*,{jong},{company},*,*,*,*")

    # NNG 일반명사 (금융 용어)
    # NNG left-id: 1785, right-id: T=3540 / F=3539
    for term in NNG_TERMS:
        last = term[-1]
        jong = 'T' if has_jongseong(last) else 'F'
        rid  = 3540 if jong == 'T' else 3539
        csv_lines.append(f"{term},1785,{rid},-5000,NNG,*,{jong},{term},*,*,*,*")
        
    tmp_dir  = tempfile.mkdtemp()
    csv_path = os.path.join(tmp_dir, 'financial.csv')
    dic_path = os.path.join(tmp_dir, 'financial.dic')

    with open(csv_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(csv_lines) + '\n')

    _mecab.cli.dict_index([
        '--dicdir', DIC_PATH,
        '--model',  str(mecab_ko_dic.model_path),
        '-f', 'utf-8', '-t', 'utf-8',
        '-u', dic_path, csv_path,
    ])
    return dic_path


@st.cache_resource(show_spinner="MeCab 초기화 중…")
def get_mecab():
    import mecab
    dic_path = _build_user_dic()
    return mecab.MeCab(user_dictionary_path=dic_path)


# ── 한자어 판별 데이터 ──────────────────────────────────────────────────────── # 사용자 사전으로 사용 가능
FINANCIAL_SINO = {
    '감면','철회','재개','이관','회신','도래','무방','상응','양지','내방','당사',
    '상이','귀사','유효','일자','상기','본','불원','불가','기거래',
    '추징','양지','수신','재개','고지','경과','당일','익일','영업일','본인','타인',
    '면책','지급','잔존','잔여','잔금','선납','후납','분납','일괄',
    '이월','이연','공제','차감','가산','합산','총액','명의','대행','수탁',
}
FINANCIAL_COMPANIES = {
    '삼성증권','미래에셋증권','KB증권','키움증권','한국투자증권','신한투자증권',
    '하나증권','대신증권','NH투자증권','메리츠증권','교보증권','카카오페이증권','토스증권',
    'KB국민은행','신한은행','하나은행','우리은행','NH농협은행','IBK기업은행',
    '케이뱅크','카카오뱅크','토스뱅크','수협은행','SC제일은행',
    '삼성카드','현대카드','KB국민카드','신한카드','롯데카드','우리카드','하나카드','BC카드',
}
FINANCIAL_AFFIX = {
    '비','가','구','기','미','불','비','재','전','본','동','타','익'
}

# ── 하십시오체 판별 기준 ──
# ① EF 단독: 습니다/습니까/십시오 계열
HAPSHO_EF_SUFFIX = ('습니다','습니까','십시오','십니다','십니까','읍니다','읍니까')
# ② VV+EF / XSV+EF / XSA+EF / VX+EF: surface가 ㅂ니다/ㅂ니까로 끝나는 경우 하십시오체
#    예) 바랍니다(VV+EF), 드립니다(VV+EF), 됩니다(XSV+EF), 합니다(XSV+EF)
HAPSHO_COMPOUND_POS = {'VV+EF', 'XSV+EF', 'XSA+EF', 'VX+EF'}
HAPSHO_BNIDA_SUFFIX = ('니다','니까')  # VV/XSV/XSA/VX+EF surface 공통 suffix (바랍니다/드립니다/됩니다/합니다 등)

# ── 해요체 판별 기준 ──
HAEYO_SUFFIX = ('어요','아요','해요','세요','게요','네요','죠','여요','래요','까요','나요')

SPEECH_COLOR = {'하십시오체':'#185FA5','해요체':'#0F6E56','혼용':'#BA7517','반말':'#7B4FBF','명사형':'#B05520','기타':'#888780'}
SPEECH_BG    = {'하십시오체':'#E6F1FB','해요체':'#E1F5EE','혼용':'#FAEEDA','반말':'#F0EAFB','명사형':'#FAEEE6','기타':'#F1EFE8'}
SPEECH_CLASS = {'하십시오체':'badge-blue','해요체':'badge-green','혼용':'badge-amber','반말':'badge-purple','명사형':'badge-orange','기타':'badge-gray'}

BANMAL_SUFFIX = ('해','어','아','지','거든','잖아','야','냐','이냐','구나','다','자','렴','려무나')

# ── 분석 함수 ─────────────────────────────────────────────────────────────────

def is_sino(word, pos):
    if pos not in ('NNG', 'NNP', 'XPN'): return False
    if word in FINANCIAL_COMPANIES: return False
    if word in FINANCIAL_SINO: return True
    if word in FINANCIAL_AFFIX: return True
    return False

def classify_ending(surface: str, pos: str) -> str:
    """종결어미 하나의 문체 수준 반환: '하십시오체' | '해요체' | '기타'"""
    if pos in ('EF', 'EP+EF'):
        if any(surface.endswith(p) for p in HAPSHO_EF_SUFFIX): return '하십시오체'
        if any(surface.endswith(p) for p in HAEYO_SUFFIX):     return '해요체'
        if any(surface.endswith(p) for p in BANMAL_SUFFIX):    return '반말'
    if pos in HAPSHO_COMPOUND_POS:
        if any(surface.endswith(p) for p in HAPSHO_BNIDA_SUFFIX): return '하십시오체'
        if any(surface.endswith(p) for p in HAEYO_SUFFIX):        return '해요체'
    return '기타'

def speech_level(ending_pairs: list, morphs: list) -> str:
    """[(surface, pos), ...] 에서 전체 문체 수준 결정"""
    lvls = set()
    for surface, pos in ending_pairs:
        c = classify_ending(surface, pos)
        if c in ('하십시오체', '해요체', '반말'): lvls.add(c)
    if len(lvls) >= 2: return '혼용'
    if lvls: return lvls.pop()
    # 종결어미 없음 — 명사형 종결어미(ETN) 또는 마지막 형태소가 명사(NNG/NNP/NP)면 명사형
    NOUN_ENDINGS = ('음','ㅁ','기')   # ETN 명사형 전성어미 surface
    PUNCT_POS    = {'SF','SP','SS','SE','SO','SW','SB'}
    content_morphs = [mo for mo in morphs if mo.feature.pos not in PUNCT_POS]
    if content_morphs:
        last = content_morphs[-1]
        # ETN(명사형 전성어미)으로 끝나는 경우
        if last.feature.pos == 'ETN':
            return '명사형'
        # ETN이 어미와 결합된 복합 태그 (e.g. XSV+ETN)
        if 'ETN' in last.feature.pos:
            return '명사형'
        # surface가 명사형 어미인 경우 (음/ㅁ/기)
        if last.surface in NOUN_ENDINGS:
            return '명사형'
        # 마지막 형태소가 명사인 경우
        if last.feature.pos in ('NNG','NNP','NP','NNB','XSN'):
            return '명사형'
    return '기타'

def analyze_sentence(sentence: str, m) -> dict:
    morphs = m.parse(sentence)
    sino, ending_pairs, hons = [], [], []
    for mo in morphs:
        w, pos = mo.surface, mo.feature.pos
        if is_sino(w, pos):
            sino.append(w)
        # 종결어미: EF 단독 + EP+EF + VV/XSV/XSA/VX+EF
        if pos in ('EF', 'EP+EF') or pos in HAPSHO_COMPOUND_POS:
            ending_pairs.append((w, pos))
        # 높임 선어말어미
        if pos == 'EP' and w in ('시', '셨'):
            hons.append(w)
        elif 'EP' in pos and pos != 'EP+EF' and ('시' in w or '셨' in w):
            hons.append(w)
    hons = list(dict.fromkeys(hons))
    final_endings = [w for w, _ in ending_pairs]
    return {
        'sino_words':          list(dict.fromkeys(sino)),
        'sino_count':          len(set(sino)),
        'final_endings':       final_endings,
        'ending_pairs':        ending_pairs,
        'speech_level':        speech_level(ending_pairs, morphs),
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
    st.markdown("## 라이팅 문체 분석기")
    st.caption("형태소 분석 기반 · Google 스프레드시트 연동")
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
                st.error(f"불러오기 실패: HTTP {e.response.status_code} — 공유 설정을 확인해 주세요.")
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
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 전체 요약", "📂 유형 / 프로세스", "🔢 빈도 분석", "📝 문장별 결과", "🔬 형태소 원시 결과"])

    # ── 탭1: 전체 요약 ────────────────────────────────────────────────────────
    with tab1:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("분석 문장 수",     f"{n}개")
        c2.metric("문장당 평균 한자어", f"{avg_sino}개")
        c3.metric("높임 선어말어미",   f"{len(all_hon)}회")
        c4.metric("종결어미 총계",     f"{len(all_endings)}회")

        st.markdown("#### 문체 수준 분포")

        DONUT_LEVELS = [
            ('하십시오체', '#185FA5'),
            ('해요체',    '#0F6E56'),
            ('혼용',      '#BA7517'),
            ('반말',      '#7B4FBF'),
            ('명사형',    '#B05520'),
            ('기타',      '#888780'),
        ]

        level_cnts  = {lvl: speech_counts.get(lvl, 0) for lvl, _ in DONUT_LEVELS}
        level_rates = {lvl: pct(cnt, n) for lvl, cnt in level_cnts.items()}

        # conic-gradient 세그먼트 누적
        segs, acc = [], 0
        for lvl, color in DONUT_LEVELS:
            r = level_rates[lvl]
            segs.append(f'{color} {acc}% {acc + r}%')
            acc += r
        conic = ','.join(segs)

        # 범례 HTML
        legend_html = ''
        for lvl, color in DONUT_LEVELS:
            cnt  = level_cnts[lvl]
            rate = level_rates[lvl]
            legend_html += (
                f'<div style="display:flex;align-items:center;gap:7px">'
                f'<div style="width:10px;height:10px;border-radius:2px;background:{color};flex-shrink:0"></div>'
                f'<span>{lvl}</span>'
                f'<strong style="margin-left:4px;color:{color}">{rate}%</strong>'
                f'<span style="color:#bbb;font-size:12px">({cnt}건)</span></div>'
            )

        st.markdown(
            f'<div style="display:flex;align-items:center;gap:24px;margin:12px 0 20px;padding:16px 20px;'
            f'background:#fafaf8;border-radius:12px;border:0.5px solid rgba(0,0,0,0.07)">'
            f'<div style="flex-shrink:0;width:120px;height:120px;border-radius:50%;'
            f'background:conic-gradient({conic});position:relative">'
            f'<div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);'
            f'width:70px;height:70px;border-radius:50%;background:white;'
            f'display:flex;flex-direction:column;align-items:center;justify-content:center">'
            f'<div style="font-size:18px;font-weight:700;color:#1a1a18;line-height:1">{n}</div>'
            f'<div style="font-size:9px;color:#aaa;margin-top:2px">문장</div>'
            f'</div></div>'
            f'<div style="display:flex;flex-direction:column;gap:8px;font-size:13px">{legend_html}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        st.markdown("#### 높임 선어말어미 사용률")
        st.caption(f"높임 표현('시/셨')이 포함된 문장: {hon_sents}개 ({pct(hon_sents, n)}%)")
        st.progress(pct(hon_sents, n) / 100)

    # ── 탭2: 유형 / 프로세스 문체 교차 분석 ─────────────────────────────────
    with tab2:
        SPEECH_LEVELS = ['하십시오체', '해요체', '혼용', '반말', '명사형', '기타']
        LEVEL_COLORS  = ['#185FA5',   '#0F6E56', '#BA7517', '#7B4FBF', 'B05520', '#888780']

        def cross_table(group_key):
            """유형 또는 프로세스별 문체 분포 테이블 반환"""
            groups = sorted(set(r[group_key] for r in analyzed if r[group_key]))
            rows_data = []
            for grp in groups:
                grp_rows = [r for r in analyzed if r[group_key] == grp]
                total_g  = len(grp_rows)
                sl_cnt   = Counter(r['_analysis']['speech_level'] for r in grp_rows)
                rows_data.append((grp, total_g, sl_cnt))
            return rows_data

        def render_cross(rows_data, title):
            if not rows_data:
                st.caption(f"{title} 데이터 없음")
                return
            st.markdown(f"**{title}**")
            for grp, total_g, sl_cnt in rows_data:
                with st.container():
                    st.markdown(
                        f'<div style="font-size:13px;font-weight:500;margin:10px 0 6px">' +
                        f'{grp} <span style="font-size:12px;font-weight:400;color:#888">({total_g}개)</span></div>',
                        unsafe_allow_html=True,
                    )
                    cols = st.columns(len(SPEECH_LEVELS))
                    for col, lvl, color in zip(cols, SPEECH_LEVELS, LEVEL_COLORS):
                        cnt  = sl_cnt.get(lvl, 0)
                        rate = pct(cnt, total_g)
                        bg   = SPEECH_BG.get(lvl, '#F1EFE8')
                        col.markdown(
                            f'<div style="background:{bg};border-radius:10px;padding:10px 12px;text-align:center">' +
                            f'<div style="font-size:11px;color:{color};font-weight:500;margin-bottom:4px">{lvl}</div>' +
                            f'<div style="font-size:20px;font-weight:600;color:{color}">{cnt}</div>' +
                            f'<div style="font-size:11px;color:#aaa;margin-top:2px">{rate}%</div>' +
                            f'</div>',
                            unsafe_allow_html=True,
                        )
            st.markdown("<br>", unsafe_allow_html=True)

        st.markdown(
            f'<div class="section-note">전체 수집 데이터 <strong>{len(results)}개</strong> · 유형·프로세스별 문체 사용 비율</div>',
            unsafe_allow_html=True,
        )
        render_cross(cross_table('_type'),    "유형별 문체 분포")
        st.divider()
        render_cross(cross_table('_process'), "프로세스별 문체 분포")

    # ── 탭3: 빈도 분석 ───────────────────────────────────────────────────────
    with tab3:
        SPEECH_LEVELS = ['하십시오체', '해요체', '혼용', '반말', '명사형', '기타']
        LEVEL_COLORS  = ['#185FA5',   '#0F6E56', '#BA7517', '#7B4FBF', 'B05520', '#888780']
        LEVEL_BG      = ['#E6F1FB',   '#E1F5EE', '#FAEEDA', '#F0EAFB', '#FAEEE6', '#F1EFE8']

        st.markdown(
            f'<div class="section-note">전체 수집 데이터 <strong>{len(results)}개</strong> 기준 · 문체 사용 비중 진단</div>',
            unsafe_allow_html=True,
        )

        def render_speech_ratio(group_key, group_label):
            groups = sorted(set(r[group_key] for r in analyzed if r[group_key]))
            if not groups:
                st.caption(f"{group_label} 데이터 없음")
                return

            st.markdown(f"**{group_label}별 문체 비중**")

            for grp in groups:
                grp_rows = [r for r in analyzed if r[group_key] == grp]
                total_g  = len(grp_rows)
                sl_cnt   = Counter(r['_analysis']['speech_level'] for r in grp_rows)

                # 그룹 헤더
                st.markdown(
                    f'<div style="font-size:13px;font-weight:500;margin:14px 0 8px">'
                    f'{grp} <span style="font-size:12px;font-weight:400;color:#888">({total_g}개 문장)</span></div>',
                    unsafe_allow_html=True,
                )

                # 하십시오체 / 해요체 비중 강조 카드
                cols = st.columns(len(SPEECH_LEVELS))
                for col, lvl, color, bg in zip(cols, SPEECH_LEVELS, LEVEL_COLORS, LEVEL_BG):
                    cnt  = sl_cnt.get(lvl, 0)
                    rate = pct(cnt, total_g)
                    col.markdown(
                        f'<div style="background:{bg};border-radius:10px;padding:14px 12px;text-align:center">'
                        f'<div style="font-size:11px;color:{color};font-weight:500;margin-bottom:6px">{lvl}</div>'
                        f'<div style="font-size:28px;font-weight:700;color:{color};line-height:1">{rate}%</div>'
                        f'<div style="font-size:11px;color:#aaa;margin-top:4px">{cnt}건</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

# 원형 그래프
                g_cnts  = {lvl: sl_cnt.get(lvl, 0) for lvl, _ in DONUT_LEVELS}
                g_rates = {lvl: pct(cnt, total_g) for lvl, cnt in g_cnts.items()}

                segs, acc = [], 0
                for lvl, color in DONUT_LEVELS:
                    r = g_rates[lvl]
                    segs.append(f'{color} {acc}% {acc + r}%')
                    acc += r
                conic_g = ','.join(segs)

                legend_g = ''
                for lvl, color in DONUT_LEVELS:
                    cnt  = g_cnts[lvl]
                    rate = g_rates[lvl]
                    legend_g += (
                        f'<div style="display:flex;align-items:center;gap:7px">'
                        f'<div style="width:10px;height:10px;border-radius:2px;background:{color};flex-shrink:0"></div>'
                        f'<span>{lvl}</span>'
                        f'<strong style="margin-left:4px;color:{color}">{rate}%</strong>'
                        f'<span style="color:#bbb">({cnt}건)</span></div>'
                    )

                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:24px;margin:12px 0 20px;padding:16px 20px;'
                    f'background:#fafaf8;border-radius:12px;border:0.5px solid rgba(0,0,0,0.07)">'
                    f'<div style="flex-shrink:0;width:100px;height:100px;border-radius:50%;'
                    f'background:conic-gradient({conic_g});position:relative">'
                    f'<div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);'
                    f'width:58px;height:58px;border-radius:50%;background:white;'
                    f'display:flex;flex-direction:column;align-items:center;justify-content:center">'
                    f'<div style="font-size:15px;font-weight:700;color:#1a1a18;line-height:1">{total_g}</div>'
                    f'<div style="font-size:9px;color:#aaa;margin-top:2px">문장</div>'
                    f'</div></div>'
                    f'<div style="display:flex;flex-direction:column;gap:7px;font-size:12px">{legend_g}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        tab3_sub1, tab3_sub2 = st.tabs(["유형별", "프로세스별"])
        with tab3_sub1:
            render_speech_ratio('_type',    '유형')
        with tab3_sub2:
            render_speech_ratio('_process', '프로세스')
            
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

# ── 탭5: 형태소 원시 결과 ────────────────────────────────────────────────
    with tab5:
        st.caption("MeCab 형태소 분석 원시 결과 CSV 다운로드")

        if filtered:
            import io as _io, csv as _csv
            raw_rows = []
            for r in filtered:
                morphs = get_mecab().parse(r['_sentence'])
                tagged = ' '.join(
                    f"{mo.surface}/{mo.feature.pos}"
                    for mo in morphs
                )
                raw_rows.append({
                    '유형':       r['_type'],
                    '프로세스':    r['_process'],
                    '문장':       r['_sentence'],
                    '형태소_분석': tagged,
                    '분석_문체':   r['_analysis']['speech_level'] if r['_analysis'] else '',
                    '종결어미':    ' / '.join(r['_analysis']['final_endings']) if r['_analysis'] else '',
                })
            buf = _io.StringIO()
            writer = _csv.DictWriter(buf, fieldnames=raw_rows[0].keys())
            writer.writeheader()
            writer.writerows(raw_rows)
            st.download_button(
                label="📥 형태소 분석 결과 CSV 다운로드",
                data=buf.getvalue().encode('utf-8-sig'),
                file_name="morpheme_raw.csv",
                mime="text/csv",
            )
        else:
            st.caption("분석된 문장이 없습니다.")

if __name__ == "__main__":
    main()
