import http.client

conn = http.client.HTTPConnection("192.168.254.60:5002")

payload = "---\n- name: Apply rate limiting on DNS server\n  hosts: 192.168.254.48\n  become: true\n  tasks:\n    - name: Install iptables-persistent package (Debian/Ubuntu)\n      package:\n        name: iptables-persistent\n        state: present\n      when: ansible_os_family == 'Debian'\n\n    - name: Install iptables-services package (CentOS/RHEL)\n      package:\n        name: iptables-services\n        state: present\n      when: ansible_os_family == 'RedHat'\n\n    - name: Configure iptables rate limiting rule for DNS\n      iptables:\n        table: filter\n        chain: INPUT\n        protocol: TCP\n        destination_port: 23\n        match: limit\n        limit: 72\n        jump: ACCEPT\n      notify:\n        - Save iptables rules\n\n    - name: Save iptables rules\n      command: iptables-save > /etc/iptables/rules.v4\n      notify:\n        - Restart iptables service\n      \n\n  handlers:\n    - name: Restart iptables service (Debian/Ubuntu)\n      service:\n        name: iptables-persistent\n        state: restarted\n      when: ansible_os_family == 'Debian'\n\n    - name: Restart iptables service (CentOS/RHEL)\n      service:\n        name: iptables\n        state: restarted\n      when: ansible_os_family == 'RedHat'\n"

headers = {
    'Content-Type': "text/yaml",
    'User-Agent': "insomnia/9.2.0"
    }

conn.request("POST", "/v2/horse/rtr_request?target_ip=192.168.254.48&service=DNS&actionType=DNS_RATE_LIMIT&actionID=%3F%3F%3F&target_port=22", payload, headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
