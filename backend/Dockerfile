FROM python:3.14
WORKDIR /code
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt
COPY ./thames_tide_times /code/thames_tide_times
CMD ["fastapi", "run", "thames_tide_times/app.py", "--port", "80"]