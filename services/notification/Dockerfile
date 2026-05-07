FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir redis requests
COPY . .
CMD ["python", "main.py"]
