FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/Rome
ENV PYTHONPATH=/app/nfvcl-ng/src/nfvcl

RUN apt-get update && \
    apt-get -y dist-upgrade && \
    apt-get -y install curl gnupg2 software-properties-common lsb-release git wget sshpass && \
    rm -rf /var/lib/apt/lists/*
# Installing python and poetry
RUN apt-add-repository --yes ppa:ansible/ansible && \
    add-apt-repository --yes ppa:deadsnakes/ppa && \
    apt-get update && apt install -y ansible && \
    apt-get install -y python3.12 python3.12-dev python3.12-venv uvicorn build-essential && \
    echo "[defaults]\nhost_key_checking = False" >> /etc/ansible/ansible.cfg && \
    curl -sSL https://install.python-poetry.org | python3 -
# Installing Helm
RUN apt-get install apt-transport-https --yes && \
    curl -fsSL https://packages.buildkite.com/helm-linux/helm-debian/gpgkey | gpg --dearmor | tee /usr/share/keyrings/helm.gpg > /dev/null && \
    echo "deb [signed-by=/usr/share/keyrings/helm.gpg] https://packages.buildkite.com/helm-linux/helm-debian/any/ any main" | tee /etc/apt/sources.list.d/helm-stable-debian.list && \
    apt-get update && \
    apt-get install -y helm
# Cleaning apt
RUN apt-get clean all -y && \
    rm -rf /var/lib/apt/lists/*
# Installing ansible plugins
RUN ansible-galaxy collection install vyos.vyos && \
    ansible-galaxy collection install prometheus.prometheus && \
    ansible-galaxy collection install git+https://github.com/s2n-cnit/nfvcl-ansible-collection.git,v0.0.1

COPY . /app/nfvcl-ng

WORKDIR /app/nfvcl-ng
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.12 1 && \
    /root/.local/bin/poetry install && \
    rm -rf /root/.cache/pypoetry/cache && \
    rm -rf /root/.cache/pypoetry/artifacts && \
    rm -rf /root/.cache/pip

CMD ["/root/.local/bin/poetry", "run", "python", "-m", "nfvcl_rest"]
