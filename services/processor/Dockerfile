FROM python:3.11-alpine
ENV PYTHONUNBUFFERED=1

RUN mkdir /service
COPY ./processor /service/processor
COPY ./pyproject.toml /service/pyproject.toml
WORKDIR /service

RUN pip install .

CMD ["python", "-m", "processor"]
