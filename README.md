# AI 뉴스 브리핑

매일경제 · 한국경제의 **최근 3일간 AI 관련 기사**를 자동으로 수집해 **3줄 요약**으로 보여주는 웹앱입니다.

- 서비스: https://20260927v.vercel.app
- 스택: Python Flask · Supabase (PostgreSQL) · Vercel (Serverless + Cron) · Vanilla JS

## 동작 방식

```
Google News RSS (site:mk.co.kr / site:hankyung.com, 3일, AI 키워드)
   └─ 헤드라인에 AI 관련 키워드가 있는 기사만 후보로 저장 (Supabase: articles, status=pending)
        └─ 리다이렉트 링크 → 원문 URL 복원 → 본문 추출 → 3줄 요약 → status=done
```

- **요약 엔진**: `ANTHROPIC_API_KEY`가 설정되어 있으면 Claude(`claude-opus-5`)가 요약하고,
  없으면 키워드 빈도 기반 핵심 문장 추출로 요약합니다 (외부 서비스 없이 동작).
- **자동 갱신**: 페이지를 열면 새 기사를 확인하고 대기 중인 기사를 순차 요약합니다.
  Vercel Cron이 매일 07:00 KST에 `/api/cron`을 호출해 새 기사를 수집하고 7일 지난 기사를 정리합니다.

## API

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/api/articles?source=&search=` | 최근 3일 기사 목록 (출처 필터 · 검색) |
| GET | `/api/stats` | 건수/요약 진행률/요약 엔진 |
| GET | `/api/health` | DB 연결 상태 |
| POST | `/api/refresh` | 새 기사 수집 + 일부 요약 |
| POST | `/api/process` | 대기 중인 기사 요약 (시간 예산 내에서 병렬 처리) |
| GET | `/api/cron` | Vercel Cron 진입점 |

## 로컬 실행

```bash
pip install -r requirements.txt
# .env.local 에 DATABASE_URL (및 선택적으로 ANTHROPIC_API_KEY) 설정
python app.py            # http://localhost:5000
python verify_app.py     # API 검증
```

## 환경변수

| 이름 | 필수 | 설명 |
|---|---|---|
| `DATABASE_URL` | ✅ | Supabase 풀러 접속 문자열 (`postgresql://...pooler.supabase.com:6543/postgres?sslmode=require`) |
| `ANTHROPIC_API_KEY` | ✗ | 설정 시 Claude AI 요약 사용 |
| `REQUEST_TIME_BUDGET` | ✗ | 요청당 처리 시간 예산(초, 기본 8) |
| `PROCESS_PARALLEL` | ✗ | 동시 처리 기사 수 (기본 6) |
| `CRON_SECRET` | ✗ | 설정 시 `/api/cron` 호출에 `Authorization: Bearer` 필요 |
