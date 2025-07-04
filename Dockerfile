FROM python:3.9 AS builder

WORKDIR /demostand

RUN apt-get update
RUN apt update && apt install -y zip htop screen libgl1-mesa-glx libfreetype6-dev

COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

CMD ["uvicorn", "server_fapi:app", "--host", "0.0.0.0", "--port", "3003"]
