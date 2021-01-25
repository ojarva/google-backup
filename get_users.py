"""
Gets list of users from Google Apps.

"""

import logging
import logging.handlers
import random
import sys
import time

import apiclient
import apiclient.discovery
import httplib2
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage

logger = logging.getLogger('google-user-list')
logger.setLevel("INFO")
handler = logging.handlers.SysLogHandler(address='/dev/log')
formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


def get_users(domain):
    storage = Storage('get_users_credentials')
    scopes = ('https://www.googleapis.com/auth/admin.directory.user.readonly')
    credentials = storage.get()
    if not credentials:
        flow = flow_from_clientsecrets('client_secrets.json', scope=scopes, redirect_uri='urn:ietf:wg:oauth:2.0:oob')
        auth_uri = flow.step1_get_authorize_url()
        print(auth_uri)
        code = raw_input("Auth token: ")
        credentials = flow.step2_exchange(code)
        storage.put(credentials)

    http = httplib2.Http()
    http = credentials.authorize(http)

    service = apiclient.discovery.build("admin", 'directory_v1', http=http)

    users = []
    next_page_token = None
    while True:
        for retrycount in range(1, 4):
            try:
                users_page = service.users().list(
                    fields='nextPageToken,users(primaryEmail,suspended,suspensionReason)',
                    domain=domain,
                    pageToken=next_page_token,
                    maxResults=500
                ).execute()
                next_page_token = users_page.get("nextPageToken")
                users_page = users_page.get("users")
                users.extend(users_page)
                break
            except IOError:
                logger.warning("Downloading list of users failed")
                time.sleep(retrycount)
        if not next_page_token:
            break
    users_filtered = []
    for user in users:
        if not user.get("suspended", True):
            users_filtered.append(user["primaryEmail"])
    random.shuffle(users_filtered)

    return users_filtered


def usage():
    print("""
Usage: %s <domain>

Prints list of non-suspended users from Google Apps in random order
""")


def main():
    if len(sys.argv) == 1:
        usage()
        sys.exit(1)
    for domain in sys.argv[1:]:
        users = get_users(domain)
        for item in users:
            print item


if __name__ == '__main__':
    main()
