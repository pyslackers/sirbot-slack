FROM python:3.6-alpine

RUN apk add --update --no-cache gcc g++ && pip install dumb-init
RUN apk add --update --no-cache libxml2-dev libxslt-dev

WORKDIR /app

COPY requirements requirements
RUN pip install -r requirements/requirements.txt

COPY . .
RUN python3 -m pip install .

COPY docker.yml /etc/sirbot.yml

ENTRYPOINT ["/usr/local/bin/dumb-init", "--"]
CMD ["/bin/sh", "-c", "sirbot -c /etc/sirbot.yml --update && exec sirbot -c /etc/sirbot.yml"]
