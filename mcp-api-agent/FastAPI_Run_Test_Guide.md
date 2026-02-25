# FastAPI MCP Agent Run & Test Guide

이 문서는 FastAPI 기반 MCP 에이전트 서버를 실행하고 테스트하는 방법을 설명합니다.

## 1. 환경 준비

먼저 필요한 패키지를 설치해야 합니다.

```bash
pip install -r requirements_api.txt
```

## 2. 서버 실행 명령어

`api_server.py`가 있는 디렉토리에서 다음 명령어를 실행합니다.

### 기본 실행 (uvicorn 직접 사용)
```bash
uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
```
- `--reload`: 코드 변경 시 서버가 자동으로 재시작됩니다.
- `--host 0.0.0.0`: 외부 접속을 허용합니다. (로컬 테스트만 할 경우 `127.0.0.1`)

### Python으로 실행
파일 하단에 `if __name__ == "__main__":` 블록이 있으므로 파이썬으로 직접 실행도 가능합니다.
```bash
python api_server.py
```

## 3. API 테스트 방법

윈도우 PowerShell이나 API 테스트 도구(Postman 등)를 사용하여 테스트할 수 있습니다.

### A. 일반 채팅 Endpoint (`/api/chat`)
단순한 질문-답변 테스트에 적합합니다.

**PowerShell (Invoke-RestMethod):**
```powershell
$body = @{ message = "현재 K8s 클러스터의 모든 네임스페이스를 보여줘" } | ConvertTo-Json -Compress
Invoke-RestMethod -Uri "http://localhost:8000/api/chat" -Method Post -Body $body -ContentType "application/json"
```

**curl (Windows CMD/PowerShell):**
```bash
curl -X POST "http://localhost:8000/api/chat" ^
     -H "Content-Type: application/json" ^
     -d "{\"message\": \"현재 K8s 클러스터의 모든 네임스페이스를 보여줘\"}"
```

### B. OpenAI 호환 Endpoint (`/v1/chat/completions`)
OpenWebUI 등 기존 UI 도구와 연동할 때 사용하며, 스트리밍 답변을 제공합니다.

**PowerShell:**
```powershell
$body = @{
    model = "qwen-k8s-agent"
    messages = @(@{ role = "user"; content = "K8s 클러스터 상태 요약해줘" })
} | ConvertTo-Json -Compress
Invoke-RestMethod -Uri "http://localhost:8000/v1/chat/completions" -Method Post -Body $body -ContentType "application/json"
```

## 4. 참고 사항
- **MCP 서버 상태**: 서버 시작 시 `config.json`에 정의된 MCP 서버들에 연결을 시도합니다. MCP 서버들이 실행 중이어야 도구를 정상적으로 불러올 수 있습니다.
- **로그**: 서버 터미널에서 실시간으로 에이전트의 사고 과정(Planning, Worker 실행 등)을 확인할 수 있습니다.
