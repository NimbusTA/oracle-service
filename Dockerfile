FROM python:3.9-slim as builder

RUN apt-get update \
 && apt-get install -y gcc \
 && rm -rf /var/lib/apt/lists/*

WORKDIR app
COPY requirements.txt ./
RUN pip install --user --trusted-host pypi.python.org -r requirements.txt
COPY . /app

FROM python:3.9-slim as app

COPY --from=builder /root/.local /root/.local

ENV PATH=/root/.local/bin:$PATH

ARG PROMETHEUS_METRICS_PORT=8001
ENV PROMETHEUS_METRICS_PORT=$PROMETHEUS_METRICS_PORT
EXPOSE ${PROMETHEUS_METRICS_PORT}

WORKDIR /oracle
COPY assets ./assets
COPY oracle ./oracle
COPY run.sh run.sh

CMD ["bash", "run.sh"]
