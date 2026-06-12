FROM python:3.14 AS base
WORKDIR /code
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt
COPY ./thames_tide_times /code/thames_tide_times

FROM base AS test
COPY ./requirements_test.txt /code/requirements_test.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements_test.txt
COPY ./tests /code/tests
ENTRYPOINT ["pytest", "/code/tests/"]

FROM base AS production
CMD ["fastapi", "run", "thames_tide_times/app.py", "--port", "80"]