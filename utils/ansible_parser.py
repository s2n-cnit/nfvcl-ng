import json


def find_task(ansible_output, task_name):
    if isinstance(ansible_output, str):
        output = json.load(ansible_output)
    else:
        output = ansible_output

    task = None
    for p in output['plays']:
        task = next((item for item in p if item['task']['name'] == task_name), None)
        if task is not None:
            break
    if task is None:
        raise ValueError('ansible output cannot be parsed')
    return task


def find_host(task, host_name):
    host = next((item for item in task['hosts'] if item == host_name), None)
    if host is None:
        raise ValueError('host not found in ansible output')
    return task['hosts'][host]


def get_stdout_lines(task, host_name):
    host = find_host(task, host_name)
    if 'stdout_lines' in host:
        return host['stdout_lines']
    else:
        return []
