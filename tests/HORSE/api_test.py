import os
import time
import unittest
import uuid
from http.server import HTTPServer
from multiprocessing import Process, Pipe
from multiprocessing.connection import Connection

from nfvcl_horse.models.horse_models import RTRActionType

# Need to be before
os.environ['HORSE_DEBUG'] = "True"
os.environ.get('HORSE_DEBUG')
# Need to be after, requires env var
from tests.HORSE.dummy_server import HTTPDummyServer, set_pipe

HTTP_DUMMY_SRV_PORT = 9995
PLAYBOOK_FILE = "tests/HORSE/test_files/test_playbook.yaml"
action_id = str(uuid.uuid4())
action_type = RTRActionType.TEST
target_ip_external = "10.145.212.201"
service_type = "DNS"


class UnitTestHorseAPIs(unittest.TestCase):
    http_dummy_server = None
    process: Process = None
    old_ip: str = None
    old_path: str = None
    parent_conn: Connection
    child_conn: Connection

    @classmethod
    def setUpClass(cls):
        """
        Start a dummy server acting as DOC module, the dummy server reflects every request
        Creates a pipe between dummy server (another process) and this one
        """
        cls.parent_conn, cls.child_conn = Pipe()
        server_address = ('', HTTP_DUMMY_SRV_PORT)
        set_pipe(cls.child_conn)
        http_dummy_server = HTTPServer(server_address, HTTPDummyServer)
        logging.info(f'Starting dummy server on port {HTTP_DUMMY_SRV_PORT}')
        cls.process = Process(target=http_dummy_server.serve_forever, args=())
        cls.process.start()

    @classmethod
    def tearDownClass(cls):
        # Stops the dummy server
        logging.info('Stopping dummy http server\n')
        cls.process.terminate()
        cls.process.join()
        cls.process.close()
        cls.process = None

    def test_000_set_doc_ip(self):
        """
         Test IP DOC setup and save the old one.
         """
        doc_module_info = get_extra("doc_module")
        if doc_module_info is None:
            set_doc_ip_port(f"127.0.0.1:{HTTP_DUMMY_SRV_PORT}", "/api/test")
            doc_module_info = get_extra("doc_module")

        self.old_ip = doc_module_info['ip'] if 'ip' in doc_module_info is not None else "127.0.0.1"
        self.old_path = doc_module_info['url_path'] if doc_module_info['url_path'] else "/"
        set_doc_ip_port(f"127.0.0.1:{HTTP_DUMMY_SRV_PORT}", "/api/test")
        # Check that they changed
        doc_module_info = get_extra("doc_module")
        self.old_ip = doc_module_info['ip']
        self.old_path = doc_module_info['url_path']
        self.assertEqual(f"127.0.0.1:{HTTP_DUMMY_SRV_PORT}", doc_module_info['ip'])
        self.assertEqual("/api/test", doc_module_info['url_path'])

    def test_001_test_workaround_forwarding(self):
        """
        Test the forwarding to DOC workaround
        """
        # Load test playbook
        path = Path(PLAYBOOK_FILE)
        yaml_text = path.read_text()
        # Fake request to dummy server
        result = rtr_request_workaround(target_ip_external, RTRActionType.DNS_RATE_LIMIT, "urs", "pwd", True, yaml_text, service=service_type, actionID=action_id)
        # Building a copy of the request
        request = build_request_for_doc(actionid=action_id, target=target_ip_external, actiontype=RTRActionType.DNS_RATE_LIMIT, service=service_type, playbook=yaml_text)
        # -------------- Assertions
        time.sleep(2)
        # What is received by dummy server is in the pipe
        received = self.parent_conn.recv()
        # What is received should be always equal to the request, given the same input
        self.assertEqual(received, request.model_dump_json())

    def test_002_test_workaround_apply(self):
        """
        Test the application on localhost that MUST fail with a certain error.
        It is impossible to include a target where playbook is applied during test.
        This test is looking that the error is the expected one.
        """
        path = Path(PLAYBOOK_FILE)
        yaml_text = path.read_text()
        try:
            result = rtr_request_workaround("127.0.0.1", RTRActionType.TEST, "test", "testpassword", False, yaml_text)
        except HTTPException as http_exc:
            if http_exc.status_code == 500:
                logging.info("TEST on workaround done")
            else:
                raise ValueError(f"HTTPException should give 500 error code. Actual value is {http_exc.status_code}")
        except Exception as e:
            raise ValueError("Unexpected exception")

    def test_003_test_forwarding(self):
        """
        Test the forwarding to DOC
        """
        # Load test playbook
        path = Path(PLAYBOOK_FILE)
        yaml_text = path.read_text()
        # Fake request to dummy server
        result = rtr_request(target_ip=target_ip_external, target_port="", service=service_type, actionType=action_type, actionID=action_id, payload=yaml_text)
        # Building a copy of the request
        request = build_request_for_doc(actionid=action_id, target=target_ip_external, actiontype=RTRActionType.TEST, service=service_type, playbook=yaml_text)
        # -------------- Assertions
        time.sleep(2)
        # What is received by dummy server is in the pipe
        received = self.parent_conn.recv()
        # What is received should be always equal to the request, given the same input
        self.assertEqual(received, request.model_dump_json())

    def test_004_test_apply(self):
        """
        Test the application on localhost that MUST fail with a certain error.
        It is impossible to include a target where playbook is applied during test.
        This test is looking that the error is the expected one.
        """
        # Load test playbook
        path = Path(PLAYBOOK_FILE)
        yaml_text = path.read_text()
        try:
            result = rtr_request("127.0.0.1", "", "DNS", RTRActionType.TEST, str(uuid.uuid4()), yaml_text)
        except HTTPException as http_exc:
            if http_exc.status_code == 500:
                logging.info("TEST on workaround done")
            else:
                raise ValueError(f"HTTPException should give 500 error code. Actual value is {http_exc.status_code}")
        except Exception as e:
            raise ValueError("Unexpected exception")

    def test_100_reset_doc_ip(self):
        """
        Restore DOC IP before tests.
        """
        set_doc_ip_port(self.old_ip, self.old_path)
        doc_module_info = get_extra("doc_module")
        self.assertEqual(self.old_ip, doc_module_info['ip'])
        self.assertEqual(self.old_path, doc_module_info['url_path'])
