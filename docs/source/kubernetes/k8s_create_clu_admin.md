# Create Cluster Admin for Kubectl
Use you API client to request at `/k8s/{cluster_id}/user/{username}` the creation of a user to be used with `kubectl`. 
The `{cluster_id}` is the `name` field in the kubernetes cluster list (You can retrieve the list using `/v1/topology/`).

The response will contain:
- The cluster certificate
- The user private key
- The user certificate

You will need to copy the response and save it (in `response.json` file) on the machine with witch you want to control your kubernetes cluster.
Remember the username, it will be needed in next steps.

Now, the just created user has no permission over the cluster. To let it manage the cluster, you will need to use the
REST `/k8s/{cluster_id}/roles/cluster-admin/{user}` using the same data as the previous call.

Then, in the same folder, create a `python` script with this content:
> |:warning:| Kubectl should be already installed and working.

```python
import base64
import json
import subprocess
from pathlib import Path

RESP_FILE = Path.cwd() / Path("response.json")
WORKING_DIR = Path.home() / Path(".kube/certificates/")
WORKING_DIR.mkdir(exist_ok=True)
CERT_FILE = WORKING_DIR / Path("cluster_cert.crt")
USER_KEY = WORKING_DIR / Path("user_key_b64.key")
USER_CERT = WORKING_DIR / Path("user_priv_cert.crt")

def write_to_file(file_name, content):
    file = open(file_name, "w")
    file.write(content)
    file.close()

if __name__ == "__main__":
    username: str = input("Enter the username: ")
    server_address: str = input("Enter the server address: ")
    server_port: str = input('Enter server port (default 6443): ').strip() or "6443"

    file = open(RESP_FILE, "r")
    data = json.load(file)

    cluster_cert = data['cluster_cert']
    write_to_file(CERT_FILE, base64.b64decode(cluster_cert).decode('utf-8'))

    user_key_b64 = data['user_key_b64']
    write_to_file(USER_KEY, base64.b64decode(user_key_b64).decode('utf-8'))

    user_priv_cert_b64 = data['user_priv_cert_b64']
    write_to_file(USER_CERT, base64.b64decode(user_priv_cert_b64).decode('utf-8'))

    set_cluster = subprocess.run(["kubectl", "config", "set-cluster", "bluecluster", "--embed-certs", f"--certificate-authority={CERT_FILE.absolute()}", f"--server=https://{server_address}:{server_port}"])
    set_cred = subprocess.run(["kubectl", "config", "set-credentials", f"{username}", f"--client-key={USER_KEY.absolute()}", f"--client-certificate={USER_CERT.absolute()}"])
    set_cont = subprocess.run(["kubectl", "config", "set-context", f"{username}@bluecluster", "--cluster=bluecluster", f"--user={username}"])
    use_cont = subprocess.run(["kubectl", "config", "use-context", f"{username}@bluecluster"])
```

Run the script `python3 script.py` it will ask for the remote username (the same used before), IP and PORT. 
Kubectl should be set up and working.
