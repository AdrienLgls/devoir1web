FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api8inf349 ./api8inf349
COPY setup.py .

ENV FLASK_APP=api8inf349
ENV FLASK_DEBUG=True

EXPOSE 5000

CMD ["flask", "run", "--host=0.0.0.0"]
