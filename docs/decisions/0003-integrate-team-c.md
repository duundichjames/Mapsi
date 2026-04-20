# ADR 0003 — Team C 의 본 구현 통합 (cherry-pick 합성 머지)

상태: Accepted (2026-04-20, `feature/integrate-c` 시점)
관련: ADR 0001, ADR 0002, `docs/module_map.md`,
원격 브랜치 `origin/feature/cli`, `origin/feature/math`, `origin/feature/packaging`

## 배경

`feature/core-engine` 에는 B 가 코어 엔진을 빠르게 굴리기 위해 만든
**임시 stub/구현** 이 7 개 모듈에 들어 있었다 (계약 1, 2, 3, 4, 5, 7).
이후 Team C 가 본인 영역 3 개 (`feature/cli`, `feature/math`,
`feature/packaging`) 를 같은 main (`ee8661f`) 에서 분기해 본 구현을
완성했다.

두 가지 고민:

1. C 의 본 구현 quality 가 우리 임시 구현보다 일부 영역에서 분명히 좋다
   (특히 `packager.py` 의 mimetype 검증/garbage 필터, `config.py` 의
   role 화이트리스트/whitespace 검증, `bindata.py` 의 SHA256 dedup).
2. 하지만 우리 임시 구현에는 C 가 모르는 후속 합의가 들어 있다 — `.env`
   가 셸 환경보다 우선해야 한다는 운영 정책 (`mapsi/cli.py`), dry-run 이
   `build_section` 까지 호출해야 한다는 회귀 정책 (Phase 6\~9 골든 픽스처
   유지를 위해 필수).

## 결정

**Cherry-pick + 합성 머지 (옵션 A)** 로 통합한다. 단순 `theirs` 채택도,
단순 `ours` 유지도 아님.

* `feature/core-engine` 위에 `feature/integrate-c` 브랜치를 분기하고,
* C 의 3 개 commit (`9a32956`, `542d6e1`, `1446d46`) 을 시간 순으로
  cherry-pick 하면서 각 충돌을 의도에 맞게 수동 합성한다.
* C 의 author/날짜는 cherry-pick 으로 그대로 보존된다.

## 모듈별 합성 규칙

| 모듈 | 결정 | 이유 |
| --- | --- | --- |
| `mapsi/packager.py` | C 채택 | mimetype 시그니처 검증 + 8 필수 파일 사전 검증 + garbage 필터 (`.DS_Store`, `__MACOSX/`) 가 명백히 우월 |
| `mapsi/builder/bindata.py` | C 채택 | SHA256 콘텐츠 해싱으로 동일 이미지 dedup, NFC unicode 파일명 정규화 |
| `mapsi/builder/manifest.py` | C 채택 | `isEmbeded="1"` 을 `BinData/` 항목에만 정확히 부여, 전용 검증 함수 보유 |
| `mapsi/config.py` | C 채택 | role 화이트리스트, whitespace 검증, `paragraph` 필수 검사, 에러 메시지가 경로까지 포함 |
| `mapsi/math/converter.py` | **합성** (B 베이스 + C 프롬프트) | B 의 Anthropic→OpenAI 폴백 체인과 cache marker 일관성을 유지하되, C 의 LaTeX↔HNC 예시 5 쌍을 시스템 프롬프트로 흡수 |
| `mapsi/cli.py` | **합성** (C 베이스 + B 두 가지 보존) | C 의 입력 검증/exit code/환경 복원을 베이스로 채택. 그 위에 B 의 `_load_dotenv_if_available()` 호출 + dry-run 의 `build_section` 까지 검증하는 `_run_dry_run()` 합성 |
| `tests/test_cli.py` | **합성** (B 5개 + C 5개) | B 의 `.env` 우선 정책 회귀 5 개 + C 의 `main()` E2E 5 개를 한 파일에 두 섹션으로 통합 |
| `tests/test_config.py` | C 신규 추가 | 7 개 케이스, 우리에게 없던 검증 |
| `tests/test_packager.py` | C 신규 추가 | 7 개 케이스, 우리에게 없던 검증 |
| `tests/test_bindata.py` | C 채택 | C 가 더 풍부 |
| `tests/test_manifest.py` | C 채택 | C 가 더 풍부 |
| `tests/test_math.py` | B 채택 | B 가 더 풍부 (29 케이스 vs C 의 ~20) |

## 보존해야 했던 핵심 invariant

Cherry-pick 중 절대 잃으면 안 되었던 것들:

1. `_load_dotenv_if_available()` — `.env` 가 셸 환경보다 우선
   (`override=True`) + base URL 안전망. 다른 도구용 `OPENAI_API_KEY` 가
   가짜 OpenAI 엔드포인트로 우리 키를 가로채는 사고를 막는 정책.
2. dry-run 의 `build_section()` 호출 — styles.yaml 매핑 누락이나 figure
   src 누락 같은 빌드 단계 오류도 dry-run 에서 잡혀야 한다는 회귀 정책
   (Phase 6\~9 골든이 이걸 전제로 함).
3. 우리 `mapsi/math/cache.py` 의 `cache_key(latex, display)` 2-인자
   시그니처. C 의 converter 가 1-인자로 호출하던 부분이 충돌의 원인이
   될 수 있어 우리 converter 베이스를 유지하는 것으로 자연 해소.

## 결과

* `feature/integrate-c` 에서 `pytest` 294 통과 (B 의 281 + C 의 신규 13).
* Phase 6\~9 골든 9 개 그대로 그린.
* README 의 CLI 5 예시 (`기본`, `--no-llm`, `--verbose`, `--dry-run`,
  `--style-map`) + 통합 데모 (`output/playground/sample.md`) 회귀 그린.
* C 의 3 commit 이 `이다현 <cad2365@naver.com>` author 로 보존됨.

## 대안과 기각 이유

* **옵션 B — 파일 직접 교체**: C 의 commit 을 무시하고 `git show` 로 추출한
  파일만 덮어 씀. 가장 빠르지만 C 의 기여가 git history 에서 사라지고
  공동 작업 신뢰가 깨진다.
* **옵션 C — C 가 main 에 먼저 머지된 뒤 우리가 rebase**: C 의 main PR 이
  올라올 때까지 대기 필요. 그 사이 `feature/core-engine` 의 후속 작업
  (Phase 10 인라인 서식, Phase 11 CP4 통합 골든) 이 멈춤.

옵션 A 가 history 보존, 충돌 통제, 일정 모두에서 가장 균형이 좋다.
