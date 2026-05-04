FROM python:3.11-slim

WORKDIR /service

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --force-reinstall --no-cache-dir opencv-python-headless

COPY . .

CMD ["python", "main.py"]
