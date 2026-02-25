FROM python:3.11-slim

# 필요 패키지 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONUNBUFFERED=1

# 의존성 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY . .

# 예시 설정을 기본 설정으로 복사 (K8s 등에서 덮어쓰지 않을 경우를 대비한 기본값)
RUN cp config.example.py config.py

# 컨테이너 실행 시 main.py 실행
ENTRYPOINT ["python", "main.py"]
