# Source sync — 2026-09-09

## 기준과 범위

- 서비스 저장소: `sport-data-hub`
- 확인한 기본 브랜치: `main`
- 소스 커밋: `09717e89bbfd60f58a251e551fbecba18e71bd18`
- 소스 커밋 시각: 2026-09-08 13:09:56 UTC
- 갱신 전 showcase 커밋: `55703e630b1b7ba3ba148335e0fd0f1803bf4a69`
- 재확인 시에도 두 저장소의 기본 브랜치 커밋이 같음을 확인했습니다.

이 문서는 비공개 운영 소스를 공개하는 대신 **구현된 기능, 데이터 흐름, 설계 판단**을 설명합니다. 예제는 독립적으로 축약·재구성했습니다. 자격증명, 운영 사용자 데이터와 전체 production 코드는 포함하지 않습니다.

## 소스와 설명의 대응

아래 경로는 비공개 서비스 저장소 안의 경로입니다.

| 반영 항목 | 확인한 구현 |
|---|---|
| 전체 일정의 월·일 보기, URL 날짜·뷰 | `frontend/src/pages/schedule-page.tsx` |
| 경기 상세 네 탭, 득점·이닝 필터, 라이브 갱신 | `frontend/src/pages/game-detail-page.tsx`, `frontend/src/features/mlb/game/game-tabs.tsx` |
| 팀 라인업, 타순별 출전·OPS·변화 | `frontend/src/pages/team-detail-page.tsx`, `frontend/src/features/mlb/team/lineup-tab.tsx` |
| 마트 우선, 적재일 이후 등판 보완, 원천 폴백 | `backend/services/mlb/pitch.py`, `backend/services/mlb/pitch_mart.py` |
| 실버 128열·버전 2 | `backend/models/mlb/silver.py` |
| 투구 마트 41열·버전 2, 정렬·행 그룹 | `backend/models/mlb/mart.py` |
| 실버 완결성 확인·시즌 재빌드·장부 갱신 | `backend/batch/mlb/mart.py` |
| 전체 경기 원문과 평탄화 이벤트의 별도 저장 | `backend/batch/mlb/play_event.py`, `backend/warehouse/r2.py` |
| 종료 상세 압축·버전·보관 범위·재조립 | `backend/services/mlb/game_detail.py`, `backend/batch/mlb/game.py` |
| 1GB 창고 머신·최근 3일 자동 처리·상세 재조립 트리거 | `backend/router/internal/jobs.py`, `frontend/worker/index.ts` |
| 연기·재개일 카드와 월간 미확정 범위 조회 | `backend/services/mlb/game.py` |
| 60초 스코어보드·10분 일정/마트 장부 | `backend/cache/ttl.py` |
| 제품 목적·다종목 방향·미구현 분석 기능 | `PRODUCT.md`, `ROADMAP.md`, `frontend/src/lib/sports.ts` |

## 문서와 구현이 다른 부분의 처리

- 제품 문서의 일정 “월·주·일” 표기와 달리, 실제 화면은 **월·일** 두 가지이므로 그 기준을 따랐습니다.
- 일부 코드 주석의 마트 “40열”, 이전 showcase의 실버 “127열”은 현재 스키마 정의의 **41열·128열**로 맞췄습니다.
- “원천은 배치만 호출”은 목표입니다. 현재 코드에는 등판 목록, 마트 이후 경기, 라이브, 미저장 상세와 폴백 호출이 남아 있어 실제 경로를 명시했습니다.
- “마트가 다음 단계”와 “원문 JSON을 보관하지 않음”은 더 이상 현재 상태가 아닙니다.
- Savant의 수비·주루·배트 트래킹 데이터는 소스 로드맵의 조사 결과를 반영하되, 실제 서비스 연동 완료로 쓰지 않았습니다.
- 기존 캐시 사례의 “6/28 = 18%”는 산술상 일치하지 않아 약 21.4%로 바로잡았습니다.
- 저장 크기·속도·비용의 과거 실험 수치를 현재 운영 수치와 구분했습니다. 서로 범위가 다른 용량 값을 전체 창고 크기로 합치지 않았습니다.

## 검증 범위

현재 소스의 라우트·화면·서비스·배치·스키마·캐시 설정을 대조했습니다. showcase 예제 5개의 Python 구문과 상대 문서 링크를 검사하고, 독립 실행 예제 3개의 실행 결과를 확인했습니다.

마트 예제는 날짜별 파일 결합·투구 행 선택·열 이름·정렬·값 보존·NULL 경기 유형을 확인하고, 조회 예제는 마트 경계 날짜·최근 N경기·원천 폴백·빈 결과·부분 실패를 확인합니다. 실버 예제는 기존 행 수·파생값·누락 열 NULL 검사를 유지합니다.

운영 배포·실제 데이터 적재율·지연 시간·인프라 비용을 이번 작업에서 측정한 것은 아닙니다. 비공개 백엔드 전체 테스트나 운영 UI 검증을 실행했다고 주장하지 않습니다. 현재 구현 상태와 향후 계획은 [Roadmap](roadmap.md)에 구분했습니다.
