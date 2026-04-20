# Mapsi 아키텍처 다이어그램

> Mapsi 전체 시스템을 한눈에 파악하기 위한 Mermaid 다이어그램 모음.
> Figma / FigJam 에 바로 붙여넣기 가능하며, GitHub / Notion / VS Code 프리뷰에서도 그대로 렌더링된다.

## 0. 한 장으로 보는 개요

![Mapsi Architecture](./architecture.png)

> Figma 에서는 `architecture.png` 를 드래그 앤 드롭하거나, 아래 Mermaid 코드 블록을
> *Mermaid Chart* 플러그인에 붙여 넣어 벡터 형태로 재생성할 수 있다.

---

## 1. 전체 아키텍처 (High-level)

```mermaid
flowchart TB
    subgraph UI["사용자 진입점 (Entry Points)"]
        direction LR
        CLI["mapsi CLI<br/>python -m mapsi"]
        ST["Streamlit UI<br/>streamlit_app.py<br/>파일/텍스트/ZIP 업로드"]
    end

    subgraph ORCH["오케스트레이션"]
        CONV["converter.md_to_hwpx()<br/>5단계 파이프라인 지휘자"]
    end

    subgraph IN["① 입력 처리"]
        direction TB
        PARSE["parser.py<br/>markdown-it-py<br/>→ Block 리스트"]
        WALK["ast_walker.py<br/>캡션 승격 · 참고문헌 demote<br/>· 각주 흡수"]
    end

    subgraph BUILD["② 빌드 (Block → HWPX XML)"]
        direction TB
        SECTION["builder/section.py<br/>role 별 dispatch"]
        ELEMENTS["builder/elements.py<br/>hp:p · hp:run · hp:tbl · hp:pic"]
        HEADER["builder/header.py<br/>header.xml 파싱 → style 테이블"]
        EQUATION["builder/equation.py<br/>hp:equation (v0.2)"]
        BINDATA["builder/bindata.py<br/>PNG/JPG → work_dir/BinData/"]
        MANIFEST["builder/manifest.py<br/>content.hpf 의 opf:manifest 갱신"]
    end

    subgraph HELPERS["스타일 룩업 보조"]
        direction LR
        CONFIG["config.py<br/>styles.yaml 로더"]
        STYLES["styles.py<br/>role+depth → 스타일 이름"]
        INLINE["inline_styles.py<br/>인라인 마크 → charPrIDRef"]
    end

    subgraph MATH["수식 LLM"]
        direction LR
        MCONV["math/converter.py<br/>LaTeX → HNC 마커<br/>Anthropic → OpenAI → 폴백"]
        MCACHE["math/cache.py<br/>~/.mapsi/equation_cache.json"]
    end

    subgraph PACK["③ 패키징"]
        PACKAGER["packager.py<br/>work_dir → ZIP<br/>(mimetype 무압축 첫 엔트리)"]
    end

    subgraph DATA["데이터 / 스펙 (코드 아님)"]
        direction LR
        TEMPL["templates/<br/>header.xml · mimetype · META-INF"]
        SPEC["spec/styles.yaml<br/>role → 스타일 이름"]
        SAMPLES["samples/base/unpacked/<br/>secPr · settings.xml · content.hpf"]
    end

    subgraph VALID["검증 도구"]
        direction LR
        INSPECT["mapsi/inspect.py<br/>HWPX 스타일·텍스트 덤프"]
        XMLVAL["validate_xml.py<br/>골든 XML 대조"]
    end

    INPUT[(input.md)] --> CLI
    INPUT --> ST
    CLI --> CONV
    ST --> CONV

    CONV --> PARSE --> WALK --> SECTION
    CONV --> HEADER
    CONV --> BINDATA --> MANIFEST

    SECTION --> ELEMENTS
    SECTION -.uses.-> HEADER
    SECTION -.uses.-> STYLES
    ELEMENTS -.uses.-> INLINE
    ELEMENTS -.equations.-> MCONV
    ELEMENTS -.equation XML.-> EQUATION

    CONFIG --> STYLES
    STYLES -.NFC 정규화.-> HEADER
    MCONV <--> MCACHE

    SECTION --> PACKAGER
    BINDATA --> PACKAGER
    MANIFEST --> PACKAGER

    TEMPL -.bootstrap.-> CONV
    SPEC -.로드.-> CONFIG
    SAMPLES -.bootstrap.-> CONV

    PACKAGER --> OUT[(output.hwpx<br/>HWPX ZIP)]
    OUT -.검증.-> INSPECT
    OUT -.검증.-> XMLVAL

    classDef entry fill:#E3F2FD,stroke:#1565C0,color:#0D47A1
    classDef orch fill:#FFF3E0,stroke:#E65100,color:#BF360C
    classDef input fill:#F3E5F5,stroke:#6A1B9A,color:#4A148C
    classDef build fill:#E8F5E9,stroke:#2E7D32,color:#1B5E20
    classDef helper fill:#FCE4EC,stroke:#AD1457,color:#880E4F
    classDef math fill:#E0F7FA,stroke:#00838F,color:#006064
    classDef pack fill:#FFF8E1,stroke:#F9A825,color:#F57F17
    classDef data fill:#ECEFF1,stroke:#455A64,color:#263238
    classDef valid fill:#EDE7F6,stroke:#4527A0,color:#311B92
    classDef io fill:#FAFAFA,stroke:#616161,color:#212121,stroke-dasharray: 5 5

    class CLI,ST entry
    class CONV orch
    class PARSE,WALK input
    class SECTION,ELEMENTS,HEADER,EQUATION,BINDATA,MANIFEST build
    class CONFIG,STYLES,INLINE helper
    class MCONV,MCACHE math
    class PACKAGER pack
    class TEMPL,SPEC,SAMPLES data
    class INSPECT,XMLVAL valid
    class INPUT,OUT io
```

---

## 2. 데이터 흐름 (Block → HWPX)

```mermaid
flowchart LR
    MD[("input.md")]
    B1["Block 리스트<br/>(평탄)"]
    B2["Block 리스트<br/>(문맥 규칙 적용)"]
    SEC["section0.xml<br/>(bytes)"]
    WD[("work_dir/<br/>Contents/ · BinData/ · META-INF/")]
    HWPX[("output.hwpx")]

    MD -->|parser.py<br/>markdown-it-py + 플러그인| B1
    B1 -->|ast_walker.py<br/>4개 규칙| B2
    B2 -->|builder/section.py<br/>role 별 dispatch| SEC

    B2 -.figure 블록.-> BD["bindata.py<br/>PNG/JPG 복사"]
    BD -->|BinData/imageN.*| WD
    BD -->|entry dict| MF["manifest.py<br/>opf:item 삽입"]
    MF -->|content.hpf 갱신| WD

    B2 -.equation_marks.-> MC["math.converter<br/>convert_equation()"]
    MC -.MAPSI_NO_LLM=1.-> FB["폴백:<br/>LaTeX 원문 마커"]
    MC -.Anthropic/OpenAI OK.-> OK["HNC 스크립트"]
    FB --> SEC
    OK --> SEC

    SEC --> WD
    WD -->|packager.py<br/>mimetype 무압축 첫 엔트리| HWPX
```

---

## 3. `--no-llm` 폴백 경로

```mermaid
flowchart TD
    USER[["사용자:<br/>mapsi input.md --no-llm"]]
    CLI["cli.py<br/>args.no_llm = True"]
    ENV["os.environ['MAPSI_NO_LLM'] = '1'"]
    CONV["converter.md_to_hwpx()"]
    PARSE["parser.py<br/>equation_marks 수집"]
    BUILD["builder/elements.py<br/>_make_run_with_equations"]
    MCONV["math/converter.convert_equation()"]
    BRANCH{"MAPSI_NO_LLM?"}
    WRAP["_wrap(latex.strip())<br/>= '[hnc 수식]LaTeX원문[/hnc 수식]'"]
    CACHE["~/.mapsi/<br/>equation_cache.json"]
    ANTHRO["Anthropic API<br/>claude-sonnet"]
    OPENAI["OpenAI API<br/>gpt-4o"]
    FALLBACK["같은 폴백<br/>= LaTeX 원문 마커"]
    HPT["<hp:t>[hnc 수식]...[/hnc 수식]</hp:t>"]

    USER --> CLI --> ENV --> CONV --> PARSE --> BUILD --> MCONV
    MCONV --> BRANCH
    BRANCH -->|Yes| WRAP
    BRANCH -->|No| CACHE
    CACHE -->|miss| ANTHRO
    ANTHRO -->|실패| OPENAI
    OPENAI -->|실패| FALLBACK
    CACHE -->|hit| HPT
    ANTHRO -->|성공| HPT
    OPENAI -->|성공| HPT
    WRAP --> HPT
    FALLBACK --> HPT

    classDef fb fill:#FFEBEE,stroke:#C62828,color:#B71C1C
    classDef ok fill:#E8F5E9,stroke:#2E7D32,color:#1B5E20
    class WRAP,FALLBACK fb
    class HPT,ANTHRO,OPENAI,CACHE ok
```

---

## 4. Streamlit UI 3-탭 플로우

```mermaid
flowchart TB
    USER((사용자))

    subgraph UI["Streamlit UI (streamlit_app.py)"]
        direction TB
        T1["탭 1: 파일 업로드<br/>.md 업로드 → 텍스트 추출"]
        T2["탭 2: 텍스트 붙여넣기<br/>text_area 입력"]
        T3["탭 3: Markdown + 이미지 ZIP<br/>.zip 업로드"]
        SB["사이드바<br/>스타일맵 경로 · --no-llm 토글<br/>업로드 캐시 관리"]
    end

    subgraph FLOW["변환 함수"]
        CMH["_convert_markdown_to_hwpx()<br/>tempdir · allow_missing_images=True"]
        CZH["_convert_zip_to_hwpx()<br/>uploads/<세션>/<br/>allow_missing_images=False"]
    end

    subgraph UPLOADS["uploads/ (프로젝트 내부, .gitignore)"]
        SESS["<timestamp>_<slug>/<br/>├── original.zip<br/>├── extract/ (md + 이미지)<br/>├── work/<br/>└── <name>.hwpx"]
        PRUNE["_prune_old_sessions()<br/>최근 10개만 유지"]
    end

    CONV["mapsi.converter.md_to_hwpx()"]
    DL[("HWPX 다운로드")]

    USER --> T1 --> CMH
    USER --> T2 --> CMH
    USER --> T3 --> CZH
    USER -.설정.-> SB
    SB -.관리.-> UPLOADS

    CMH --> CONV
    CZH --> SESS --> CONV
    CONV --> DL
    SESS -.변환 후.-> PRUNE
    SESS -.보관.-> DL

    classDef tab fill:#E3F2FD,stroke:#1565C0
    classDef flow fill:#FFF3E0,stroke:#E65100
    classDef store fill:#ECEFF1,stroke:#455A64
    class T1,T2,T3,SB tab
    class CMH,CZH,CONV flow
    class SESS,PRUNE,UPLOADS store
```

---

## 5. 모듈 레이어 요약 (Cheat Sheet)

```mermaid
flowchart TB
    subgraph L1["Layer 1 · 진입"]
        direction LR
        A1["__main__.py"]
        A2["cli.py"]
        A3["streamlit_app.py"]
    end

    subgraph L2["Layer 2 · 오케스트레이션"]
        B1["converter.py<br/>(50줄 이내, 지휘자)"]
    end

    subgraph L3["Layer 3 · 입력"]
        direction LR
        C1["parser.py<br/>(~574줄, 가장 복잡)"]
        C2["ast_walker.py"]
    end

    subgraph L4["Layer 4 · 빌드"]
        direction LR
        D1["header.py"]
        D2["section.py"]
        D3["elements.py<br/>(~1110줄, 최대)"]
        D4["bindata.py"]
        D5["manifest.py"]
        D6["equation.py (v0.2)"]
    end

    subgraph L5["Layer 5 · 패키징"]
        E1["packager.py"]
    end

    subgraph L6["Layer 6 · 보조"]
        direction LR
        F1["config.py"]
        F2["styles.py"]
        F3["inline_styles.py"]
        F4["math/converter.py"]
        F5["math/cache.py"]
        F6["inspect.py"]
    end

    L1 --> L2 --> L3 --> L4 --> L5
    L4 -.uses.-> L6
    L2 -.uses.-> L6

    classDef layer fill:#F5F5F5,stroke:#9E9E9E
    class L1,L2,L3,L4,L5,L6 layer
```

---

## Figma / FigJam 사용 팁

- **FigJam** 은 `File → Import → Mermaid` 가 있으며 위 코드 블록을 그대로 붙여넣으면 자동 변환.
- **Figma (디자인 파일)** 에서는 `Mermaid` 플러그인 (ex. *Mermaid Chart*) 설치 후 이 코드 블록을 붙여넣으면 된다.
- 같은 디렉터리의 `architecture.png` 는 렌더된 정적 이미지라 어디든 드래그해 붙이기 가능.
