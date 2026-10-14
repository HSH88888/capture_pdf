# Capture PDF

화면을 캡처하면 **바로 PDF 파일로 저장**해 주는 Windows 프로그램입니다.

## 기능

| 기능 | 단축키 |
|---|---|
| 전체 화면 캡처 (모든 모니터) | `Ctrl + Shift + 1` |
| 영역 지정 캡처 (마우스로 드래그) | `Ctrl + Shift + 2` |

- 단축키는 프로그램이 최소화되어 있어도 동작합니다 (전역 단축키).
- 캡처하면 저장 폴더에 `capture_YYYYMMDD_HHMMSS.pdf` 로 즉시 저장됩니다.
  - 기본 저장 폴더: `문서\CapturePDF` (프로그램에서 변경 가능)
- **여러 장 모아서 한 PDF로 저장**: 체크하면 캡처를 모아 두었다가 `PDF로 저장` 버튼을 누를 때 한 개의 여러 페이지 PDF로 저장합니다.
- **저장 후 PDF 바로 열기**, **캡처할 때 이 창 숨기기** 옵션
- 영역 캡처 중 `Esc` 또는 마우스 오른쪽 버튼으로 취소
- 고해상도(125%/150% 배율) 화면, 다중 모니터 지원
- 설정은 `%USERPROFILE%\.capture_pdf.json` 에 저장됩니다.

## 실행 방법

### 1) 파이썬으로 바로 실행
[Python 3.8+](https://www.python.org/downloads/) 설치 후:

```bat
pip install -r requirements.txt
python capture_pdf.py
```
또는 `run.bat` 더블클릭 (오류가 나면 창이 닫히지 않고 메시지를 보여 줍니다).

### 2) exe 파일로 만들기
`build_exe.bat` 을 더블클릭하면 `dist\CapturePDF.exe` 가 만들어집니다.
이 exe 하나만 있으면 파이썬이 없는 PC에서도 실행됩니다.

### 3) GitHub에서 exe 받기 (CI)
코드를 올릴 때마다 GitHub Actions가 Windows에서 테스트하고 exe를 자동으로 빌드합니다.
저장소의 **Actions** 탭 → 최근 실행 → 아래쪽 **Artifacts** 의 `CapturePDF` 를 받아 압축을 풀면 `CapturePDF.exe` 가 있습니다.

> 윈도우 시작 시 자동 실행하려면 `Win + R` → `shell:startup` 폴더에 exe 바로가기를 넣으세요.

## 오류가 날 때

- 오류 내용은 대화상자로 표시되고 `%USERPROFILE%\capture_pdf_error.log` 에도 기록됩니다.
- `'python'은(는) 내부 또는 외부 명령...이 아닙니다` → Python 설치 시 **Add python.exe to PATH** 를 체크하고 다시 설치하세요.
- `No module named 'PIL'` → `python -m pip install pillow`
- 단축키가 안 먹음 → 다른 프로그램이 같은 단축키를 사용 중입니다 (상태 표시줄에 표시됨).
