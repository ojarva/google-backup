"""
Downloads files from Google Drive
"""

import datetime
import json
import logging
import logging.handlers
import os
import time

import httplib

from .get_users import get_users
from .helpers import BackupBase, get_logger
from .settings import DOMAIN

SYSTEM = "drive"
logger = get_logger(SYSTEM)


class DriveBackup(BackupBase):
    def __init__(self, user_email):
        super().__init__(SYSTEM, user_email)

    FORMAT_MAPPINGS = {
        "application/vnd.google-apps.document": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.google-apps.spreadsheet": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.google-apps.presentation": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.google-apps.form": None,
        "application/vnd.google-apps.folder": None,
    }

    def initialize_service(self):
        if not os.path.exists(f"{self.rootpath}/content"):
            os.mkdir(f"{self.rootpath}/content")
        if not os.path.exists(f"{self.rootpath}/content/deleted"):
            os.mkdir(f"{self.rootpath}/content/deleted")

    def run(self):
        self.logger.info("Starting")

        service = self.impersonate_user('https://www.googleapis.com/auth/drive.readonly', 'drive', 'v2')
        start = time.time()
        total_processed = total_messages = total_skipped = 0

        try:
            with open(f"{self.rootpath}/last_fetch_time") as last_fetch_file:
                last_fetch_time = last_fetch_file.read()
        except FileNotFoundError:
            last_fetch_time = "2012-01-01T00:00:00"
        highest_modification_time = datetime.datetime.utcnow().isoformat().split(".")[0]

        query = "modifiedDate > '%s' and '%s' in owners" % (last_fetch_time, self.user_email)
        nextpagetoken = None

        while True:
            files = {}
            for retrycount in range(0, 4):
                try:
                    files = service.files().list(q=query, pageToken=nextpagetoken).execute()
                    break
                except httplib.BadStatusLine:
                    time.sleep(retrycount)
                    continue
                except Exception as err:  # pylint: disable=broad-except
                    self.logger.warning("Unhandled exception %r while downloading the file list", err)
                    time.sleep(retrycount)
                    continue
                self.logger.warning("Fetching file list failed. Dropping last fetch time back to %s", last_fetch_time)

            for item in files.get("items", []):
                mimetype = item.get("mimeType")
                format_mapping = DriveBackup.FORMAT_MAPPINGS.get(mimetype, False)
                total_messages += 1
                if format_mapping is None:
                    self.logger.debug("Skipping %s: mime %s is marked as non-downloadable" % (item.get("id"), mimetype))
                    json.dump(item, open("%s/content/%s.json" % (self.rootpath, item.get("id")), "w"))
                    total_skipped += 1
                    continue
                if format_mapping:
                    download_url = item.get("exportLinks", {}).get(DriveBackup.FORMAT_MAPPINGS.get(mimetype))
                else:
                    download_url = item.get("downloadUrl")
                if not download_url:
                    self.logger.debug("Skipping %s: no valid download url found. MIME: %s", item.get("id"), mimetype)
                    json.dump(item, open("%s/content/%s.json" % (self.rootpath, item.get("id")), "w"))
                    total_skipped += 1
                    continue
                for retrycount in range(0, 4):
                    try:
                        resp, content = service._http.request(download_url)
                        if resp.status == 200:
                            open("%s/content/%s.data" % (self.rootpath, item.get("id")), "w").write(content)
                            json.dump(item, open("%s/content/%s.json" % (self.rootpath, item.get("id")), "w"))
                            total_processed += 1
                            # For some reason, this helps with random memory leak:
                            del content
                            del resp
                            break
                        else:
                            logging.warning("Downloading %s for user %s failed", item.get("id"), self.user_email)
                            time.sleep(retrycount)
                            continue
                    except httplib.BadStatusLine:
                        time.sleep(retrycount)

            nextpagetoken = files.get("nextPageToken")
            if not nextpagetoken:
                break

        with open(f"{self.rootpath}/last_fetch_time", "w") as last_fetch_file:
            last_fetch_file.write(highest_modification_time)

        end = time.time()
        elapsed = end - start
        msgs = total_processed / elapsed
        self.logger.info(
            "Finished in %.2f seconds. Downloaded %s/%s files. %s was skipped. %.2f msg/s", elapsed, total_processed,
            total_messages, total_skipped, msgs
        )


def main():
    users = get_users(DOMAIN)
    logger.info("Running with %s users", len(users))

    for user in users:
        drivebackup = DriveBackup(user)
        drivebackup.initialize()
        drivebackup.run()


if __name__ == '__main__':
    main()
