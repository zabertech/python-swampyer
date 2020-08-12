WS_PATH = 'ws://localhost:18081/ws'

TICKET_USERNAME = 'user'
TICKET_PASSWORD = 'pass'

def get_password():
    with open('test_server/.crossbar/test-password.txt','r') as f:
        return f.read()



