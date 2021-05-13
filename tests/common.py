import six

try:
    import swampyer 
except:
    pass

TICKET_USERNAME = 'user'
TICKET_PASSWORD = 'pass'

def get_password():
    with open('test_server/.crossbar/test-password.txt','r') as f:
        return f.read()

def connect_service(
          url='ws://localhost:18080/ws',
          serializer_code=None,
          concurrency_max=None,
          concurrency_class=None,
          concurrency_configs=None,
          timeout=None
          ):
    password = get_password()
    serializers = None
    if serializer_code:
        serializers = [ serializer_code ]
    client = swampyer.WAMPClientTicket(
                    url=url,
                    username=u"test",
                    password=six.u(password),
                    realm=u"realm1",
                    uri_base="",
                    timeout=timeout,
                    serializers=serializers,
                    auto_reconnect=False,
                    concurrency_max=concurrency_max,
                    concurrency_class=concurrency_class,
                    concurrency_configs=concurrency_configs
                ).start()
    return client



