from http.server import BaseHTTPRequestHandler, HTTPServer
import logging
import urllib.parse
from multiprocessing.connection import Connection

SENTINEL = "---STOP---"

PIPE_CONNECTION: Connection = None

def set_pipe(connection: Connection):
    PIPE_CONNECTION = connection


class HTTPDummyServer(BaseHTTPRequestHandler):
    parent_conn: Connection = None
    child_conn: Connection = None
    process_id = None

    def _set_response(self):
        self.send_header('Content-type', 'application/json')
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        logging.info(f"GET request from {self.client_address[0]}")
        logging.info(f"Path: {self.path}")
        logging.info(f"Headers: {self.headers}")
        self._set_response()
        resp = "{ Received: true }"
        resp_utf8 = resp.encode('utf-8')
        self.write_to_pipe(resp)
        self.wfile.write(resp_utf8)

    def do_POST(self):
        logging.info(f"POST request from {self.client_address[0]}")
        logging.info(f"Path: {self.path}")
        logging.info(f"Headers: {self.headers}")

        cont_len = int(self.headers['Content-Length'])  # <--- Gets the size of data
        post_data = self.rfile.read(cont_len)
        body = post_data.decode('utf-8')

        logging.info(f"Body: {body}")

        decoded_string = urllib.parse.unquote(post_data)
        logging.info(decoded_string)

        self._set_response()
        self.write_to_pipe(decoded_string)
        self.wfile.write(post_data)

    def write_to_pipe(self, str_data: str):
        if PIPE_CONNECTION is None:
            logging.warning("NOT WRITING ON PIPE CAUSE IT IS NULL")
        else:
            PIPE_CONNECTION.send(str_data)

    def set_pipe(self, connection: Connection):
        self.child_conn = connection


class HTTPCustomServer(HTTPServer):
    child_conn: Connection = None

    def __init__(self, server_address, RequestHandlerClass, bind_and_activate=True, child_conn: Connection = None):
        self.child_conn = child_conn
        super().__init__(server_address, RequestHandlerClass, bind_and_activate)

    def set_pipe(self, connection: Connection):
        self.child_conn = connection
