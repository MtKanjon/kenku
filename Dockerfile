FROM python:3.11-alpine

COPY requirements.txt /opt/requirements.txt
RUN apk add --no-cache --virtual .build-deps gcc libffi-dev linux-headers make musl-dev \
 && apk add git \
 && pip install -r /opt/requirements.txt \
 && apk del .build-deps \
 && redbot-setup --no-prompt --data-path /data --backend json --instance-name kenku

COPY cogs /opt/cogs

VOLUME /data

RUN redbot kenku --no-prompt --edit --prefix '%' --edit-data-path '/data'
CMD ["redbot", "kenku", "--no-prompt"]