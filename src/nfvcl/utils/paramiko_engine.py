import paramiko

def ssh_session(hostname, port, username, password, commands):
    nbytes = 4096

    client = paramiko.Transport((hostname, port))
    client.connect(username=username, password=password)
    res=[]
    stdout_data = []
    stderr_data = []
    session = client.open_channel(kind='session')
    for command in commands:
        session.exec_command(command)
        while True:
            if session.recv_ready():
                stdout_data.append(session.recv(nbytes))
            if session.recv_stderr_ready():
                stderr_data.append(session.recv_stderr(nbytes))
            if session.exit_status_ready():
                break
        res.append({
                'status': session.recv_exit_status(),
                'command': command,
                'stdout': ''.join(stdout_data),
                'stderr': ''.join(stderr_data)
        })

    session.close()
    client.close()
    return res
