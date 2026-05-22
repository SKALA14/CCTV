FROM python:3.11-slim

WORKDIR /service

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libsm6 libxext6 libxrender1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --force-reinstall --no-cache-dir opencv-python-headless

COPY . .

CMD ["python", "main.py"]
