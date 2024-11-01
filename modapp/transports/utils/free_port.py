import socket
from contextlib import closing


def get_free_port():
    # find free port
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("localhost", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        free_port = s.getsockname()[1]
    return free_port
