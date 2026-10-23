FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd -m runner
USER runner
# v6 gVisor + seccomp
# docker run --runtime=runsc --rm --read-only --tmpfs /tmp --memory=256m --cpus=0.5 --pids-limit=64 --network=none --security-opt seccomp=seccomp.json inveniolang
CMD ["python","pruebas/conformidad.py"]

