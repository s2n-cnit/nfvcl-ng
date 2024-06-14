import os
from pathlib import Path
import logging
import time
import unittest
from http.server import HTTPServer
from multiprocessing import Process, Pipe
from multiprocessing.connection import Connection

# Need to be before
os.environ['HORSE_DEBUG'] = "True"
os.environ.get('HORSE_DEBUG')
# Need to be after, requires env var
from nfvcl.rest_endpoints.HORSE.horse import *
from tests.HORSE.dummy_server import HTTPDummyServer, set_pipe


HTTP_DUMMY_SRV_PORT = 9999

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

        self.old_ip = doc_module_info['ip'] if doc_module_info['ip'] else "127.0.0.1"
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
        path = Path("tests/HORSE/test_playbook.yaml")
        yaml_text = path.read_text()
        # Fake request to dummy server
        result = rtr_request_workaround("10.10.10.10", RTRActionType.TEST, "urs", "pwd", True, yaml_text)
        self.assertEqual(result, RTRRestAnswer(description='The request has been forwarded to DOC module.', status='forwarded', status_code=404, data={}))
        time.sleep(2)
        # What is received by dummy server is in the pipe
        received = self.parent_conn.recv()
        # What is received should be always the same, given the same input
        self.assertEqual(received, '{"actionid":"","target":"10.10.10.10","actiondefinition":{"actiontype":"TEST","service":"","action":{"zone":"TEST","status":"TEST"}}}')

    def test_002_test_workaround_apply(self):
        """
        Test the run of playbook workaround
        """
        path = Path("tests/HORSE/test_playbook.yaml")
        yaml_text = path.read_text()
        # Should be runned in localhost and have success
        result = rtr_request_workaround("127.0.0.1", RTRActionType.TEST, "test", "testpassword", False, yaml_text)
        self.assertEqual(result, RTRRestAnswer(description="Playbook applied", status="success"))


    def test_100_reset_doc_ip(self):
        """
        Restore DOC IP before test
        """
        set_doc_ip_port(self.old_ip,  self.old_path)
        doc_module_info = get_extra("doc_module")
        self.assertEqual(self.old_ip, doc_module_info['ip'])
        self.assertEqual(self.old_path, doc_module_info['url_path'])
