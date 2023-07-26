FROM opensourcemano/api-fe:15

# Libraries used by the base osm defined ee
RUN apt-get install -y software-properties-common wget \
    && apt-add-repository --yes --update ppa:ansible/ansible \
    && apt-get update && apt install -y ansible \
    && echo "host_key_checking = False" >> /etc/ansible/ansible.cfg \
    && pip3 install PyYAML && pip3 install requests && pip3 install paramiko && pip3 install jinja2 \
    && ansible-galaxy collection install vyos.vyos \
    && ansible-galaxy collection install prometheus.prometheus

EXPOSE 50051

CMD [ "bash", "-c", "while true; do /app/EE/osm_ee/scripts/ee_start.sh ; sleep 5; done" ]
