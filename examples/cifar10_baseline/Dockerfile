FROM python:3.11.14-slim
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY .labpilot-dataset/cifar-10-batches-py /datasets/cifar-10-batches-py
WORKDIR /workspace
CMD ["python", "train.py"]
