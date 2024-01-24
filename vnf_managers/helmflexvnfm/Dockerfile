FROM opensourcemano/api-fe:15

# Libraries used by the base osm defined ee
RUN apt-get install -y software-properties-common wget \
    && apt-add-repository --yes --update ppa:ansible/ansible \
    && apt-get update && apt install -y ansible \
    && echo "host_key_checking = False" >> /etc/ansible/ansible.cfg \
    && pip3 install PyYAML==6.0.1 requests==2.27.1 paramiko==3.4.0 Jinja2==3.0.3 coloredlogs==15.0.1 verboselogs==1.7 colorama==0.4.5\
    && ansible-galaxy collection install vyos.vyos \
    && ansible-galaxy collection install prometheus.prometheus

EXPOSE 50051

CMD [ "bash", "-c", "while true; do /app/EE/osm_ee/scripts/ee_start.sh ; sleep 5; done" ]
