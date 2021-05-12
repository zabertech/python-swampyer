FROM ubuntu:20.04

ARG UID=1000
ARG GID=1000

ENV DEBIAN_FRONTEND noninteractive

USER root

RUN groupadd -g ${GID} zaber \
    && useradd -m -u ${UID} -d /home/zaber -g zaber zaber \
    && apt update \
    && apt install -y software-properties-common \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt install -y \
            vim-nox \
            tmux \
            python2.7 \
            python2.7-dev \
            python3.6 \
            python3.7 \
            python3.8 \
            python3.9 \
            libxml2-dev \
            libxslt1-dev \
            build-essential \
            pypy3-dev \
            python3.6-dev \
            python3.7-dev \
            python3.8-dev \
            python3.9-dev \
            libssl-dev \
            curl \
            python3-distutils \
    && curl https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py \
    && curl https://bootstrap.pypa.io/pip/2.7/get-pip.py -o /tmp/get-pip-2.7.py \
    && python3.6 /tmp/get-pip.py -q \
    && python3.7 /tmp/get-pip.py -q \
    && python3.8 /tmp/get-pip.py -q \
    && python3.9 /tmp/get-pip.py -q \
    && python2.7 /tmp/get-pip-2.7.py \
    && pip3 install crossbar \
    && ls -l /tmp/ \
    ;

USER zaber

COPY --chown=zaber:zaber . /app
WORKDIR /app

RUN    curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python3 - \
    && /app/docker/build-envs.sh \
    ;

# Then this will execute the test command
CMD /bin/bash

