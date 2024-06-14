from http.server import BaseHTTPRequestHandler, HTTPServer
import logging
import urllib.parse
from multiprocessing.connection import Connection

SENTINEL = "---STOP---"

PIPE_CONNECTION: Connection = None

def set_pipe(connection: Connection):
    global PIPE_CONNECTION
    PIPE_CONNECTION = connection


class HTTPDummyServer(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    parent_conn: Connection = None
    child_conn: Connection = None
    process_id = None

    def _set_get_response(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def _set_post_response(self, content_length):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Content-Length', content_length)
        self.end_headers()

    def do_GET(self):
        logging.info(f"GET request from {self.client_address[0]}")
        logging.info(f"Path: {self.path}")
        logging.info(f"Headers: {self.headers}")
        self._set_get_response()
        resp = ""
        resp_utf8 = resp.encode('utf-8')
        self.write_to_pipe(resp)
        self.wfile.write(resp_utf8)

    def do_POST(self):
        logging.info(f"POST request from {self.client_address[0]}")
        logging.info(f"Path: {self.path}")
        logging.info(f"Headers: {self.headers}")

        content_length = int(self.headers['Content-Length'])  # <--- Gets the size of data
        post_data = self.rfile.read(content_length)
        body = post_data.decode('utf-8')

        logging.info(f"Body: {body}")

        decoded_string = urllib.parse.unquote(post_data)
        logging.info(decoded_string)

        self._set_post_response(content_length)
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
