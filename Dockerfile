FROM python:3.7-alpine

RUN apk add --no-cache 
  gcc \ 
  musl-dev \
  python2-dev

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

VOLUME /app

EXPOSE 5004

CMD [ "python", "./tvhProxy.py" ]
