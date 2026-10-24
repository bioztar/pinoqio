# Pinoqio judge for Plata's "A Judge That Learns from an Expert".
# Build: docker build -t pinoqio-judge .
# Adapt: docker run --rm -e GEMINI_API_KEY_JUDGE -v "$PWD/in:/input" -v "$PWD/artifacts:/artifacts" pinoqio-judge adapt
# Eval:  docker run --rm -e GEMINI_API_KEY_JUDGE -v "$PWD/in:/input" -v "$PWD/artifacts:/artifacts" -v "$PWD/out:/output" pinoqio-judge eval
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY gemma.py pipeline.py ./
ENTRYPOINT ["python", "/app/pipeline.py"]
