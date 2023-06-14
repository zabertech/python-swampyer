
import re
import sys
import json
import yaml
import uuid
import random
from pprint import pprint

from faker import Faker

locale_list = ['en-US', 'de_DE', 'en_US', 'fr_FR', 'ja_JP']

fake = Faker(locale_list)

COUNTER = 1123

groups = []
users = []

def clean_header(s):
    s = s.lower()
    s = re.sub(r"['()]",'',s)
    s = re.sub('\W+',' ',s).strip()
    s = re.sub(' ','_',s)
    return s

def fake_group():
    global COUNTER
    COUNTER += 1
    job = re.sub(r"[,()']", "", fake.job())
    group_acct = f"group-{clean_header(job)}"
    group_name = f"{job} Group"
    dn = f"CN={group_name},OU=Groups,OU=Example,DC=ad,DC=example,DC=com"

    group_rec = {
                    'attributes': {
                        'cn': [group_name],
                        'distinguishedName': [dn],
                        'groupType': [-2147483646],
                        'instanceType': [4],
                        'member': [],
                        'name': [group_name],
                        'objectCategory': ['CN=Group,CN=Schema,CN=Configuration,DC=ad,DC=example,DC=com'],
                        'objectClass': ['top', 'group'],
                        'objectGUID': [f"{{{uuid.uuid4()}}}"],
                        'objectSid': [f"S-1-5-21-4822552251-1245514515-3159472456-{COUNTER}"],
                        'sAMAccountName': [group_acct],
                        'sAMAccountType': [268435456]
                    },
                    'dn': dn
                }

    return dn, group_rec
    
def fake_user():
    global COUNTER
    COUNTER += 1

    profile = fake.profile()
    login = profile['username']


    firstname = re.sub(r"[,()]","",fake.first_name())
    lastname = re.sub(r"[,()]","",fake.last_name())
    name = f"{firstname} {lastname}"
    dn = f"{name},OU=Users,OU=Example,DC=ad,DC=example,DC=com"

    user_rec = {
                    'attributes': {
                        'cn': [ name ],
                        'codePage': [0],
                        'countryCode': [0],
                        'displayName': [name],
                        'distinguishedName': [dn],
                        'givenName': [firstname],
                        'instanceType': [4],
                        'memberOf': [],
                        'name': [name],
                        'objectCategory': ['CN=Person,CN=Schema,CN=Configuration,DC=ad,DC=example,DC=com'],
                        'objectClass': ['top',
                                        'person',
                                        'organizationalPerson',
                                        'user'],
                        'objectGUID': [f"{{{uuid.uuid4()}}}"],
                        'objectSid': [f"S-1-5-21-4822552251-1245514515-3159472456-{COUNTER}"],
                        'primaryGroupID': [513],
                        'sAMAccountName': [login],
                        'sAMAccountType': [805306368],
                        'sn': [lastname],
                        'userAccountControl': [66048],
                        'userPrincipalName': [f"{login}@ad.example.com"],
                        'mail': [f"{login}@example.com"],
                    },
                    'dn': dn,
                    'password': '',
                 }

    return dn, user_rec

def generate_mock_data(
        group_count=10,
        user_count=100,
        output_fpath='data/ldap-mock-data.yaml',
        groupings=None
    ):
    # Create groups
    groups = {}
    for i in range(group_count):
        dn, group = fake_group()
        groups[dn] = group

    # Create users
    users = {}
    for i in range(user_count):
        dn, user = fake_user()
        users[dn] = user
    users_list = list(users.values())

    # Distribute users into groups
    if groupings is None:
        groupings = [ 90, 33, 29, 23, 20, 10, 10, 5 ]
    groupings.reverse()

    member_count = 0
    for group in groups.values():
        group_dn = group['dn']
        group_members = group['attributes']['member']
        if groupings:
            member_count = groupings.pop()
        members = random.choices(users_list, k=member_count)
        for member in members:
            user_dn = member['dn']
            user_members = member['attributes']['memberOf']

            group_members.append(user_dn)
            user_members.append(group_dn)

    # And dump the data into the appropriate data failes
    with open(output_fpath,'w') as f:
        yaml.dump({
                'users': list(users.values()),
                'groups': list(groups.values()),
            }, f)


