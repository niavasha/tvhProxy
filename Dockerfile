FROM python:3.7-alpine as builder

# Dependencies are necessary for gevents, which seems to be rebuild on an alpine base image.
RUN apk add --no-cache \
      gcc \ 
      musl-dev \
      python2-dev \
    && python -m venv /opt/venv
    
# Make sure we use the virtualenv:
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.7-alpine

COPY --from=builder /opt/venv /opt/venv

# Make sure scripts in .local are usable:
ENV PATH=/root/.local/bin:$PATH

WORKDIR /usr/src/app

COPY . .

VOLUME /usr/src/app

EXPOSE 5004

CMD [ "python", "./tvhProxy.py" ]
