FROM python:3.9-alpine

RUN apk add --no-cache --virtual .build-deps gcc libffi-dev linux-headers make musl-dev \
 && apk add git \
 && pip install Red-DiscordBot \
 && apk del .build-deps

RUN redbot-setup --no-prompt --data-path /data --backend json --instance-name kenku

COPY cogs /opt/cogs
COPY requirements.txt /opt/requirements.txt
RUN pip install -r /opt/requirements.txt

VOLUME /data

CMD ["redbot", "kenku"]