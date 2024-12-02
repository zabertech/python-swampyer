import os
import pathlib
import json
import logging

import swampyer 

logger = logging.getLogger(__name__)

# Setup for proper pathing for libs and data
LIB_PATH = pathlib.Path(__file__).resolve().parent
TEST_PATH = LIB_PATH.parent
SRC_PATH = TEST_PATH.parent
DATA_PATH = pathlib.Path('/volume/nexus-test-data')

def load_nexus_db():
    """ The nexus test db should have a dump of all the roles
        users, and such at tests/data/snapshot.json
    """
    snapshot_path = DATA_PATH / 'snapshot.json'
    snapshot_fh = snapshot_path.open('r')
    snapshot_data = json.load(snapshot_fh)
    return snapshot_data

TICKET_USERNAME = 'user'
TICKET_PASSWORD = 'pass'

def connect_service(
          url='ws://NEXUS_HOST:8282/ws',
          serializer_code=None,
          concurrency_max=None,
          concurrency_class=None,
          concurrency_configs=None,
          timeout=None,
          username=None,
          password=None,
          auto_reconnect=False,
          max_payload_size=50_000_000,
          ):

    # Fixup the host
    target_host = os.environ.get('NEXUS_HOST', 'nexus_swampyer')
    url = url.replace('NEXUS_HOST', target_host)

    snapshot_data = load_nexus_db()
    users = snapshot_data['users']

    # Try to login manually
    if not username:
        username = 'backend-1'
    if password is None:
        password = users[username]['plaintext_password']

    logging.info(f"Connecting to: {username}@{url}")

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
                    auto_reconnect=auto_reconnect,
                    concurrency_max=concurrency_max,
                    concurrency_class=concurrency_class,
                    concurrency_configs=concurrency_configs,
                    max_payload_size=max_payload_size,
                ).start()
    return client

