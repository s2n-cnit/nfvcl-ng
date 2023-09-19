import http.client
import time
conn = http.client.HTTPConnection("192.168.27.14:5002")

### GET TOPO

payload = ""
conn.request("GET", "/v1/topology/", payload)
res = conn.getresponse()
topology = res.read().decode()
assert res.status==200

### DEL TOPO

payload = "{\n  \"callback\": \"http://12.1.2.1\"\n}"
headers = { 'Content-Type': "application/json" }
conn.request("DELETE", "/v1/topology/", payload, headers)
res = conn.getresponse()
res.read()
assert res.status==202

### GET TOPO

payload = ""
conn.request("GET", "/v1/topology/", payload)
res = conn.getresponse()
res.read()
assert res.status==200

### CREATE TOPO

payload = topology # Using the retrieved topology.
headers = { 'Content-Type': "application/json" }
conn.request("POST", "/v1/topology/?terraform=false", payload, headers)
res = conn.getresponse()
res.read()
assert res.status==202

### Create a VIM to be removed
payload = "{\n      \"name\": \"OS-Lab\",\n      \"vim_type\": \"openstack\",\n      \"schema_version\": \"1.0\",\n      \"vim_url\": \"http://os-lab.maas:5000/v3\",\n      \"vim_tenant_name\": \"admin\",\n      \"vim_user\": \"admin\",\n      \"vim_password\": \"pap3rin0\",\n      \"config\": {\n        \"insecure\": true,\n        \"APIversion\": \"v3.3\",\n        \"use_floating_ip\": false\n      },\n      \"networks\": [\n        \"control-os1\",\n\t\t\t\t\"radio\"\n      ],\n      \"routers\": [],\n      \"areas\": [20]\n}"
headers = { 'Content-Type': "application/json" }
conn.request("POST", "/v1/topology/vim", payload, headers)
res = conn.getresponse()
res.read()
assert res.status==202

### Delete the inserted VIM
time.sleep(0.3) # Time to make let NFVCL insert data into DB
payload = ""
conn.request("DELETE", "/v1/topology/vim/OS-Lab", payload)
res = conn.getresponse()
response = res.read()
assert res.status==202

### GET VIM
payload = ""
conn.request("GET", "/v1/topology/vim/OS-1", payload)
res = conn.getresponse()
res.read()
assert res.status==200

### UPDATE VIM (ADD area 150,250,196)
payload = "{\n  \"name\": \"OS-1\",\n  \"networks_to_add\": [],\n  \"networks_to_del\": [],\n  \"routers_to_add\": [],\n  \"routers_to_del\": [],\n  \"areas_to_add\": [150,250,196],\n  \"areas_to_del\": []\n}"
headers = { 'Content-Type': "application/json" }
conn.request("PUT", "/v1/topology/vim/OS-1", payload, headers)
res = conn.getresponse()
res.read()
assert res.status==202

### UPDATE VIM (DEL area 150,250,196)
payload = "{\n  \"name\": \"OS-1\",\n  \"networks_to_add\": [],\n  \"networks_to_del\": [],\n  \"routers_to_add\": [],\n  \"routers_to_del\": [],\n  \"areas_to_add\": [],\n  \"areas_to_del\": [150,250,196]\n}"
headers = { 'Content-Type': "application/json" }
conn.request("PUT", "/v1/topology/vim/OS-1", payload, headers)
res = conn.getresponse()
res.read()
assert res.status==202

### GET BLUEPRINTS TEST
headers = { 'Content-Type': "application/json" }
conn.request("GET", "/nfvcl/v1/api/blue/", payload, headers)
res = conn.getresponse()
res.read()
assert res.status==200
