FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

EXPOSE 7860

CMD ["python", "-m", "streamlit", "run", "景觀植物AI系統/介面/streamlit_app.py", "--server.address=0.0.0.0", "--server.port=7860", "--server.headless=true"]
