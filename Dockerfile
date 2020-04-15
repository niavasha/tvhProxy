FROM debian:latest

# Dependencies are necessary for gevents, which seems to be rebuild on an alpine base image.
RUN apt-get update && apt-get --no-install-recommends install -y \
      gcc \ 
      libffi-dev \
      musl-dev \
      python3 \
      python3-dev \
      python3-gevent \
      python3-venv \
      python3-pip \
    && python3 -m venv /opt/venv
    
# Make sure we use the virtualenv.
#ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

#FROM python:3.8-alpine

#COPY --from=builder /opt/venv /opt/venv
#COPY --from=builder /usr/lib/python3.8 /usr/local/lib/python3.8

# Make sure we use the virtualenv.
#ENV PATH="/opt/venv/bin:$PATH"

#WORKDIR /usr/src/app

COPY . .

VOLUME /usr/src/app

EXPOSE 5004

CMD [ "python3", "./tvhProxy.py" ]
