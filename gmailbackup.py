PROCNAME = True
try:
    import procname
except:
    NOPROCNAME = False

from oauth2client.client import SignedJwtAssertionCredentials
import httplib2
import logging
import logging.handlers
import multiprocessing
import os
import progressbar
import re
import subprocess
import sys
import time

from get_users import get_users
from settings import *
from helpers import BackupBase, timeit, get_logger

SYSTEM = "gmail"
logger = get_logger(SYSTEM)

class GmailBackup(BackupBase):

    def __init__(self, user_email):
        super(GmailBackup, self).__init__(SYSTEM, user_email)

    def impersonate_user(self, scope='https://mail.google.com/'):
        self.logger.debug("Impersonating user")
        f = file(SERVICE_ACCOUNT_PKCS12_FILE_PATH, 'rb')
        key = f.read()
        f.close()

        credentials = SignedJwtAssertionCredentials(SERVICE_ACCOUNT_EMAIL, key,
            scope=scope, sub=self.user_email)
        http = httplib2.Http(".cache")
        http = credentials.authorize(http)
        credentials.refresh(http)
        return credentials

    def get_offlineimap_config(self, access_token):
        self.logger.debug("Fetching config file with path %s", self.rootpath)
        #folderfilter = lambda folder: folder in ['INBOX']re.search('Gmail', folder)
        return """
[general]
accounts = Gmail-%(email)s
fsync = False


[Account Gmail-%(email)s]
localrepository = Local-%(email)s
remoterepository = Remote-%(email)s
status_backend = sqlite

[Repository Local-%(email)s]
type = Maildir
localfolders = %(rootpath)s/maildir

[Repository Remote-%(email)s]
type = IMAP
cert_fingerprint = b0ba392bba326e6feb1add4d04fa0fb86cd173fa
xoauth_access_token = %(access_token)s
remotehost = imap.gmail.com
remoteuser = %(email)s
ssl = yes
remoteport = 993
type = Gmail
readonly = True
maxconnections = 3

""" % {"email": self.user_email, "rootpath": self.rootpath, "access_token": access_token}

    def initialize_service(self):
        if not os.path.exists("%s/maildir" % self.rootpath):
            os.mkdir("%s/maildir" % self.rootpath)

    def run(self):
        if PROCNAME:
            procname.setprocname("Gmail:%s" % self.user_email)
        self.logger.info("Starting")

        usercredentials = self.impersonate_user()
        offlineimap_config = self.get_offlineimap_config(usercredentials.access_token)
        config_filename = "config_files/offlineimap_config_%s" % self.user_email
        open(config_filename, "w").write(offlineimap_config)

        command = ["/home/gmailbackup/gmailbackup/offlineimap/build/lib.linux-x86_64-2.7/offlineimaprun", "-c", config_filename, "-q"]

        p = subprocess.Popen(command, stderr=subprocess.PIPE)

        start = time.time()
        stats = {}
        total_processed = 0
        total_messages = 0

        while True:
            line = p.stderr.readline()
            if line == None or line == '':
                break
            matches = re.search(' Copy message ([0-9]+) \(([0-9]+) of ([0-9]+)\) (.*)', line)
            if not matches:
                continue
            folder_messages = matches.group(3)
            folder = matches.group(4)
            total_processed += 1
            if folder not in stats:
                stats[folder] = int(folder_messages)
                if self.queue:
                    self.queue.put(["add_total", int(folder_messages)])
                total_messages = sum(stats.values())
                self.logger.info("%s messages (%s processed)", total_messages, total_processed)
            if self.queue:
                self.queue.put(["processed"])

        ret = p.wait()
        end = time.time()
        elapsed = end - start
        msgs = total_processed / elapsed
        self.logger.info("Finished with return code %s in %.2f seconds. Downloaded %s/%s messages. %.2f msg/s", ret, elapsed, total_processed, total_messages, msgs)
        # Subtract messages not processed from progress bar.
        if self.queue:
            self.queue.put(["missed",  total_messages - total_processed])
            self.queue.put(["finished_user"])
        if PROCNAME:
            procname.setprocname("Gmail:null")
        return ret

MAX_THREADS = 5

def main_progressbar(users, q):
    finished = max_val = missed = running_processes = 0
    is_a_tty = sys.stdout.isatty()

    if is_a_tty:
        main_progress = progressbar.ProgressBar(widgets=[progressbar.SimpleProgress(), " ", progressbar.Percentage(), " ", progressbar.ETA(), " ", progressbar.FileTransferSpeed("msg")])
        main_progress.start()

    while True:
        item = q.get()
        if item[0] == "finished_user":
            users -= 1
            if users == 0:
                break
        if item[0] == "finished":
            finished += item[1]
            if is_a_tty:
                main_progress.update(finished)
        if item[0] == "add_total":
            max_val += item[1]
            if is_a_tty:
                main_progress.maxval = max_val
        if item[0] == "missed":
            max_val -= item[1]
            if is_a_tty:
                main_progress.maxval = max_val
            missed += item[1]
        if item[0] == "processed":
            finished += 1
            if is_a_tty:
                main_progress.update(finished)
        if item[0] == "quit":
            break
    self.logger.info("Finished. Downloaded %s/%s messages. Missing %s", finished, max_val, missed)
    if is_a_tty:
        main_progress.finish()


def runuser(user_email, queue):
    backup = GmailBackup(user_email)
    backup.queue = runuser.queue
    backup.initialize()
    return backup.run()

def runuser_init(queue):
    runuser.queue = queue

def main():
    if PROCNAME:
        procname.setprocname("Gmail:main")

    users = get_users(DOMAIN)

    logger.info("Running with %s users and %s threads", len(users), MAX_THREADS)

    manager = multiprocessing.Manager()
    queue = manager.Queue()
    pool = multiprocessing.Pool(MAX_THREADS, runuser_init, [queue])

    results = []

    parameters = []
    for item in users:
        parameters.append((item, queue))
        runuser_init(queue)
        print runuser(item, queue)

    try:
        r = pool.map_async(runuser, parameters, callback=results.append)
        main_progressbar(len(users), queue)
        r.wait()
    except KeyboardInterrupt:
        r.terminate()
        r.wait()


if __name__ == '__main__':
    main()
