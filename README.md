# UX 라이팅 문체 분석기

MeCab-ko 형태소 분석 기반 · Google 스프레드시트 연동 Streamlit 앱

## 파일 구성

```
ux-analyzer-streamlit/
├── app.py            # 메인 앱
├── requirements.txt  # Python 패키지
├── packages.txt      # 시스템 패키지 (MeCab)
└── README.md
```

---

## 로컬 실행

```bash
pip install -r requirements.txt
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 자동으로 열립니다.

---

## Streamlit Cloud 배포 (무료, 링크 공유)

1. **GitHub 저장소 생성** (Public 또는 Private)
2. 이 폴더의 파일 4개를 저장소에 업로드
3. [share.streamlit.io](https://share.streamlit.io) 접속 → GitHub 로그인
4. **New app** → 저장소 선택 → Main file: `app.py` → **Deploy**
5. 배포 완료 후 `https://[앱이름].streamlit.app` 링크 공유

---

## 스프레드시트 설정

- 공유 설정: **링크가 있는 모든 사용자 → 뷰어**
- 필수 열 이름 (한글 또는 영문 모두 인식):
  - `문장` 또는 `sentence`
  - `유형` 또는 `type`
  - `프로세스` 또는 `process`

---

## 분석 항목

| 항목 | 설명 |
|---|---|
| 한자어 | NNG/NNP 품사의 한자 기원 명사 |
| 종결어미 | EF 태그 기준, 합쇼체/해요체 분류 |
| 높임 선어말어미 | EP 태그의 '시/셨' 추출 |
| 문체 수준 | 합쇼체 / 해요체 / 혼용 / 없음 |
