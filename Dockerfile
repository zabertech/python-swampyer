FROM zaberit/nexus:3.0.20230620

# Make the src directory
USER root
RUN mkdir /src && chown -R zaber: /src
USER zaber

# Copy over the data files
COPY . /src

# Let's sit in the src directory by default
WORKDIR /src

ENV PATH /root/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

USER root

RUN apt update ; apt install -y software-properties-common ; add-apt-repository ppa:deadsnakes/ppa \
    && apt install -y \
            build-essential \
            curl \
            git \
            libssl-dev \
            libxml2-dev \
            libxslt1-dev \
            pypy3-dev \
            python3-distutils \
            python3.7 \
            python3.7-dev \
            python3.7-distutils \
            python3.8 \
            python3.8-dev \
            python3.8-venv \
            python3.9 \
            python3.9-dev \
            python3.10 \
            python3.10-dev \
            python3.10-distutils \
            python3.11 \
            python3.11-dev \
            python3.11-distutils \
            telnet \
            vim-nox \
    # Pip is handy to have around
    && curl https://bootstrap.pypa.io/get-pip.py -o /root/get-pip.py \
    && python3 /root/get-pip.py \
    # We also use Nox
    && python3 -m pip install nox \
    # Cleanup caches to reduce image size
    && python3 -m pip cache purge \
    && apt clean \
    && rm -rf ~/.cache \
    && rm -rf /var/lib/apt/lists/*

USER zaber

RUN echo "Installing Poetry" \
    # Poetry is used managing deps and such
    && curl -sSL https://install.python-poetry.org -o /tmp/install-poetry.py \
    && python3 /tmp/install-poetry.py \
    # SETUP Environment
    && /src/docker/setup-env.sh \
    ;

CMD /src/docker/run-test.sh

