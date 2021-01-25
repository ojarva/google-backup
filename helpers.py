import logging
import logging.handlers
import os
import pwd
import subprocess
import time
from functools import wraps

import httplib2
from apiclient.discovery import build
from oauth2client.client import SignedJwtAssertionCredentials

from .settings import *

TIMING = {}


def get_logger(system):
    logger = logging.getLogger(system)
    logger.setLevel("INFO")
    handler = logging.handlers.SysLogHandler(address='/dev/log')
    formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


def timeit(func):
    @wraps(func)
    def timer(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        name = func.__name__
        if name not in TIMING:
            TIMING[name] = []
        TIMING[name].append(end - start)
        return result

    return timer


class BackupBase(object):
    def __init__(self, system, user_email):
        self.system = system
        self.user_email = user_email
        self.zfsrootpath = "%s/%s/%s" % (ZPOOL_ROOT_PATH, system, user_email.replace("@", "__"))
        self.rootpath = "/%s" % self.zfsrootpath
        self.queue = None
        self.logger = logging.getLogger("%s.%s" % (system, user_email))
        self.timing = {}

    def print_timing(self):
        print(TIMING)

    @timeit
    def _impersonate_user(self, scope):
        assert scope

        self.logger.debug("Impersonating user %s", self.user_email)
        with open(SERVICE_ACCOUNT_PKCS12_FILE_PATH, 'rb') as f:
            key = f.read()

        credentials = SignedJwtAssertionCredentials(SERVICE_ACCOUNT_EMAIL, key, scope=scope, sub=self.user_email)
        http = httplib2.Http(".cache")
        http = credentials.authorize(http)
        credentials.refresh(http)
        return (http, credentials)

    @timeit
    def impersonate_user(self, scope, service_name, service_version=None):
        (http, _) = self._impersonate_user(scope)
        service = build(serviceName=service_name, version=service_version, http=http)
        return service

    @timeit
    def initialize(self):
        assert self.system

        if not os.path.exists(self.rootpath):
            self.logger.info("Creating %s for %s", self.rootpath, self.user_email)
            zfs_p = subprocess.Popen(["/usr/bin/sudo", "/sbin/zfs", "create", self.zfsrootpath])
            retcode = zfs_p.wait()
            if retcode != 0:
                self.logger.error("Unable to create %s for %s", self.rootpath, self.user_email)
                return False

        if not os.path.exists(self.rootpath):
            self.logger.error("Unable to create %s for %s", self.rootpath, self.user_email)
            return False

        if pwd.getpwuid(os.stat(self.rootpath).st_uid).pw_name != BACKUP_OWNER:
            chown_p = subprocess.Popen(["/usr/bin/sudo", "/bin/chown", BACKUP_OWNER, self.rootpath])
            retcode = chown_p.wait()
            if retcode != 0:
                self.logger.error("Unable to change ownership of %s to %s", self.rootpath, BACKUP_OWNER)
                return False

        try:
            self.initialize_service()
        except AttributeError:
            pass

        return True

    def run(self, *args, **kwargs):
        raise NotImplementedError("run() is not implemented")
