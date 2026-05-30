# 수식 통합 검증

한글에서 직접 열어 수식 렌더링을 확인하기 위한 문서입니다.

## 1. 네 가지 입력 구문

인라인 달러 구문: 본문 중간에 $a^2 + b^2 = c^2$ 처럼 들어갑니다.

디스플레이 달러 구문:

$$
\frac{1}{N} \sum_{n=1}^{N} x_n = \bar{x}
$$

백슬래시 인라인 구문: 원의 면적은 \(\pi r^2\) 입니다.

백슬래시 디스플레이 구문:

\[
\int_0^\infty e^{-x^2} \, dx = \frac{\sqrt{\pi}}{2}
\]

equation 환경:

\begin{equation}
E = mc^2
\end{equation}

align 환경:

\begin{align}
a &= b + c \\
d &= e - f
\end{align}

## 2. 다양한 구조

분수와 첨자(위/아래): $\frac{\partial f}{\partial x}$ 와 $x_{i}^{2}$ 입니다.

합·적분·극한: $\sum_{k=1}^{n} k$, $\int_a^b f(x) \, dx$, $\lim_{x \to 0} \frac{\sin x}{x}$.

그리스 문자: $\alpha + \beta = \gamma$, $\Delta x$, 변형 $\varepsilon$.

행렬(bmatrix):

$$ \begin{bmatrix} a & b \\ c & d \end{bmatrix} $$

cases:

$$ f(x) = \begin{cases} x & x > 0 \\ -x & x < 0 \end{cases} $$

제곱근과 n제곱근: $\sqrt{2}$ 와 $\sqrt[3]{x}$.

장식(hat/bar/vec): $\hat{x}$, $\bar{y}$, $\vec{v}$.

텍스트와 공백(틸드 변환): $\text{여러 단어}$, 그리고 $a \quad b$ 와 $a \, b$.

한글 변수명: $대위변제율_t = \frac{저신용보증액_t}{전체보증액_t} \times 100$.

## 3. 표본 복잡 수식 (역작성)

분수와 합이 중첩된 식:

$$ \hat{X}_{t+h} = \frac{1}{5} \sum_{i=1}^{5} X_{t+h-i} $$

cases 가 든 추세 조정식:

$$ \text{추세조정분}_t = \begin{cases} \frac{1}{3} \sum_{i=1}^{3} (r_{t-4+i} - r_{t-5+i}) & \text{동일 방향} \\ 0 & \text{기타} \end{cases} $$

업종 위험 가중 지수:

$$ \text{업종위험가중지수}_t = \sum_i w_{i,t} \times r_i $$

## 4. 평문과 수식이 섞인 문단

이 문단은 평문으로 시작해서 중간에 인라인 수식 $E = mc^2$ 가 자연스럽게 들어가고, 다시 평문이 이어진 뒤 또 다른 수식 $\alpha \to \beta$ 로 끝나는 혼합 문단입니다.

## 5. 미지원 명령어 폴백

가짜 명령어가 든 수식 $\foobar{x} + y$ 는 변환에 실패하여 LaTeX 원문이 보존됩니다.
