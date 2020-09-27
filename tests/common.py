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

def connect_service(url='ws://localhost:18080/ws',serializer_code='json',concurrency_max=None):
    password = get_password()
    client = swampyer.WAMPClientTicket(
                    url=url,
                    username=u"test",
                    password=six.u(password),
                    realm=u"realm1",
                    uri_base="",
                    serializers=[serializer_code],
                    auto_reconnect=False,
                    concurrency_max=concurrency_max
                ).start()
    return client



