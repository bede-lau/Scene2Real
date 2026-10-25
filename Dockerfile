FROM node:24-bookworm-slim AS node

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MUJOCO_GL=osmesa \
    SCENE2REAL_RUNS_DIR=/data/runs \
    HOME=/data

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libosmesa6 libgl1 libegl1 libglib2.0-0 tini gosu \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 scene2real \
    && useradd --uid 10001 --gid 10001 --no-create-home --home-dir /data scene2real

COPY --from=node /usr/local/bin/node /usr/local/bin/node
WORKDIR /app
COPY requirements-production.txt ./
RUN pip install --no-cache-dir -r requirements-production.txt

COPY scene2real/ ./scene2real/
COPY assets/ ./assets/
COPY static/ ./static/
COPY third_party/ ./third_party/
COPY clips/clips.json ./clips/
COPY clips/demo-set-1-west.mp4 clips/demo-set-1-center.mp4 clips/demo-set-1-east.mp4 \
     clips/demo-set-2-west.mp4 clips/demo-set-2-center.mp4 clips/demo-set-2-east.mp4 \
     clips/synthetic-warehouse-fire.mp4 ./clips/
COPY ops/site_api_proxy.mjs ops/upload_tickets.mjs ops/run_container.sh ./ops/
RUN ln -s /data/cache /app/cache

ENV SCENE2REAL_FFMPEG_THREADS=1

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','10000')+'/healthz',timeout=3)"

ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/bin/bash", "/app/ops/run_container.sh"]
