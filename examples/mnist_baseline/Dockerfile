FROM python:3.11.14-slim
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY download.py /tmp/download.py
RUN python /tmp/download.py
WORKDIR /workspace
CMD ["python", "train.py"]
