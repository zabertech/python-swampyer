import os
import pathlib
import subprocess
import socket
import time
import json
import sys
import logging
import re

# Setup for proper pathing for libs and data
LIB_PATH = pathlib.Path(__file__).resolve().parent
TEST_PATH = LIB_PATH.parent
SRC_PATH = TEST_PATH.parent
DATA_PATH = TEST_PATH / 'data'

sys.path.insert(1, f"{SRC_PATH}/lib")

def launch_nexus():
    """ This starts a copy of nexus on the local server
    """
    cwd = os.getcwd()
    os.chdir(DATA_PATH)

    cx_env = os.environ
    current_path = pathlib.Path(__file__).resolve()
    cx_env['PYTHONPATH'] = str(SRC_PATH/"lib")
    log_level = cx_env.get('LOG_LEVEL', 'warn')
    config_fpath = str(DATA_PATH/'izaber.yaml')
    cx_process =  subprocess.Popen([
                                "crossbar",
                                "start",
                                "--loglevel", log_level,
                                "--config", config_fpath
                            ], env=cx_env)

    # Wait till port 8282 is open. Give up after 60 seconds
    a_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    location = ("127.0.0.1", 8282)
    for i in range(60):
        time.sleep(1)
        result_of_check = a_socket.connect_ex(location)
        if result_of_check == 0:
            break
    else:
        print(f"Port is not open. Giving up")
        sys.exit(1)

    time.sleep(5)
    os.chdir(cwd)

    return cx_process


def load_nexus_db():
    """ The nexus test db should have a dump of all the roles
        users, and such at tests/data/snapshot.json
    """
    snapshot_path = DATA_PATH / 'snapshot.json'
    snapshot_fh = snapshot_path.open('r')
    snapshot_data = json.load(snapshot_fh)
    return snapshot_data

try:
    import swampyer 
except:
    pass

TICKET_USERNAME = 'user'
TICKET_PASSWORD = 'pass'

def connect_service(
          url='ws://localhost:8282/ws',
          serializer_code=None,
          concurrency_max=None,
          concurrency_class=None,
          concurrency_configs=None,
          timeout=None
          ):

    snapshot_data = load_nexus_db()
    users = snapshot_data['users']

    # Try to login manually
    username = 'backend-1'
    password = users[username]['plaintext_password']

    serializers = None
    if serializer_code:
        serializers = [ serializer_code ]
    client = swampyer.WAMPClientTicket(
                    url=url,
                    username=username,
                    password=password,
                    realm=u"izaber",
                    uri_base="",
                    timeout=timeout,
                    serializers=serializers,
                    auto_reconnect=False,
                    concurrency_max=concurrency_max,
                    concurrency_class=concurrency_class,
                    concurrency_configs=concurrency_configs
                ).start()
    return client

