# 파이썬 3.11 환경
FROM python:3.11-slim

# 필요한 시스템 패키지 설치 (필요시)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 의존성 설치 환경 변수 설정
ENV PYTHONUNBUFFERED=1

# requirements 먼저 복사하여 캐시 활용
COPY requirements_api.txt .
RUN pip install --no-cache-dir -r requirements_api.txt

# 애플리케이션 소스 복사
COPY . .

# config.py가 없는 경우(git ignore됨)를 대비해 example 파일을 기본 설정으로 복사하여 에러 방지
RUN cp config.example.py config.py

# FastAPI 포트 개방
EXPOSE 8000

# 컨테이너 실행 명령 (Uvicorn으로 api_server.py 실행)
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]
