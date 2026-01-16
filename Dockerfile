FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/Rome

RUN apt-get update && \
    apt-get -y dist-upgrade && \
    apt-get -y install curl gnupg2 software-properties-common lsb-release git wget sshpass && \
    rm -rf /var/lib/apt/lists/*
# Installing python and uv
RUN add-apt-repository --yes ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y python3.14 python3.14-venv python3.14-dev libffi-dev uvicorn build-essential && \
    mkdir -p /etc/ansible && echo "[defaults]\nhost_key_checking = False" >> /etc/ansible/ansible.cfg && \
    curl -LsSf https://astral.sh/uv/install.sh | sh
# Installing Helm
RUN apt-get install apt-transport-https --yes && \
    curl -fsSL https://packages.buildkite.com/helm-linux/helm-debian/gpgkey | gpg --dearmor | tee /usr/share/keyrings/helm.gpg > /dev/null && \
    echo "deb [signed-by=/usr/share/keyrings/helm.gpg] https://packages.buildkite.com/helm-linux/helm-debian/any/ any main" | tee /etc/apt/sources.list.d/helm-stable-debian.list && \
    apt-get update && \
    apt-get install -y helm
# Cleaning apt
RUN apt-get clean all -y && \
    rm -rf /var/lib/apt/lists/*

COPY . /app/nfvcl-ng

WORKDIR /app/nfvcl-ng

# Verify _version.py exists (must be generated before docker build)
# For local builds: run ./scripts/build_docker.sh
# For CI/CD: version file is generated in pipeline before docker build
RUN test -f src/nfvcl/_version.py || (echo "ERROR: src/nfvcl/_version.py not found. Run: python3 scripts/generate_version.py" && exit 1)

RUN /root/.local/bin/uv sync && \
    /root/.local/bin/uv cache clean && \
    rm -rf /root/.cache/pip

# Installing ansible plugins
RUN /root/.local/bin/uv run ansible-galaxy collection install vyos.vyos && \
    /root/.local/bin/uv run ansible-galaxy collection install prometheus.prometheus && \
    /root/.local/bin/uv run ansible-galaxy collection install git+https://github.com/s2n-cnit/nfvcl-ansible-collection.git,v0.0.1

CMD ["/root/.local/bin/uv", "run", "python", "-m", "nfvcl_rest"]
