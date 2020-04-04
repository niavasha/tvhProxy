FROM python:3.7-alpine as builder

# Dependencies are necessary for gevents, which seems to be rebuild on an alpine base image.
RUN apk add --no-cache \
  gcc \ 
  musl-dev \
  python2-dev

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt --install-option="--prefix=/install" 

FROM python:3.7-alpine

COPY --from=builder /install /usr/local

WORKDIR /usr/src/app

COPY . .

VOLUME /usr/src/app

EXPOSE 5004

CMD [ "python", "./tvhProxy.py" ]
