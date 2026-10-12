FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY config config
COPY domain domain
COPY infrastructure infrastructure
COPY data_access data_access
COPY web web
COPY run_crawl.py run_backfill.py run_dashboard.py run_backup.py ./
EXPOSE 8501
CMD ["python", "run_dashboard.py", "--server.address=0.0.0.0"]
