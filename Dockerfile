FROM ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/Rome

RUN apt-get update && \
    apt-get -y dist-upgrade && \
    apt-get -y install curl gnupg2 software-properties-common lsb-release git wget && \
    rm -rf /var/lib/apt/lists/*

RUN apt-add-repository --yes ppa:ansible/ansible && \
    add-apt-repository --yes ppa:deadsnakes/ppa && \
    apt-get update && apt install -y ansible && \
    apt-get install -y python3.11 python3.11-dev python3.11-venv python3.11-distutils uvicorn build-essential && \
    echo "[defaults]\nhost_key_checking = False" >> /etc/ansible/ansible.cfg && \
    curl -sSL https://install.python-poetry.org | python3 - && \
    apt-get clean all -y && \
    rm -rf /var/lib/apt/lists/*
# Installing ansible plugins
RUN ansible-galaxy collection install vyos.vyos && \
    ansible-galaxy collection install prometheus.prometheus && \
    ansible-galaxy collection install git+https://github.com/s2n-cnit/nfvcl-ansible-collection.git,v0.0.1

COPY . /app/nfvcl-ng

WORKDIR /app/nfvcl-ng
RUN /root/.local/bin/poetry install && \
    rm -rf /root/.cache/pypoetry/cache && \
    rm -rf /root/.cache/pypoetry/artifacts && \
    rm -rf /root/.cache/pip

CMD ["/root/.local/bin/poetry", "run", "python", "-m", "nfvcl"]
