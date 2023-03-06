# util functions for blueprints
import json


def parse_ansible_output(dict_action_output_raw: dict, playbook_name: str, task_name: str, field_name: str) -> dict:
    dict_action_output = dict_action_output_raw.copy()
    # print(dict_action_output_raw['result'])
    # dict_action_output['result'] = json.loads(dict_action_output_raw['result'])

    pb = next((item for item in dict_action_output['result'] if item['playbook'] == playbook_name), None)
    if pb is None:
        raise ValueError("Playbook {} not found in parsing Ansible output".format(playbook_name))

    task = next((item for item in pb['stdout']['plays'][0]['tasks'] if item['task']['name'] == task_name), None)
    if task is None:
        raise ValueError(
            "Task {} not found in playbook {} during Ansible output parsing".format(task_name, playbook_name))

    if field_name not in task['hosts']['host']:
        raise ValueError(
            "Field {} not found in task {} of playbook {}".format(field_name, task_name, playbook_name))

    return task['hosts']['host'][field_name]


