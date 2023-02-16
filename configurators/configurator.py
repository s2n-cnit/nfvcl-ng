from copy import deepcopy


class Configurator_Base(object):
    def __init(self, nsd_id: str, m_id: str):
        self.nsd_id = nsd_id
        self.nsd = {'member-vnfd-id': m_id}
        self.config_content = {}
        self.monitoring_tools = []

    def set_mng_ip(self, ip: str) -> None:
        self.mng_ip = ip

    def set_nsi_id(self, nsi_id: str) -> None:
        self.nsi_id = nsi_id

    def get_type(self) -> str:
        if hasattr(self, 'type'):
            return self.type
        else:
            return ""

    def dump_(self) -> list:
        res = [
            {
                'ns-name': self.nsd_id,
                'primitive_data': {
                    'member_vnf_index': self.nsd['member-vnfd-id'],
                    'primitive': 'flexops',
                    'primitive_params': {'config-content': deepcopy(self.config_content)}
                }
            }
        ]

        self.config_content = {}
        """
        if hasattr(self, "action_list"):
            if isinstance(self.action_list, list):
                self.action_list.append({"action": res, "time": now.strftime("%H:%M:%S")})
        """
        # TODO check if the following commands are needed
        if hasattr(self, "nsi_id"):
            if self.nsi_id is not None:
                for r in res:
                    r['nsi_id'] = self.nsi_id

        return res

    def destroy(self):
        return
