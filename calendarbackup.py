"""
Downloads all Google Calendar entries using Calendar API.

Only downloads calendars where user have owner access (read-write-manage). This potentially leads to duplicate downloads with shared calendars. However, typical calendars are very small,
so the only issue comes with 10k daily API quota.
"""

from get_users import get_users
import time
import datetime
import json
import logging
import logging.handlers

from settings import CALENDAR_IGNORE_USERS, DOMAIN
from helpers import BackupBase, timeit, get_logger

SYSTEM = "calendar"

logger = get_logger(SYSTEM)

class CalendarBackup(BackupBase):
    def __init__(self, user_email):
        super(CalendarBackup, self).__init__(SYSTEM, user_email)

    @timeit
    def run(self):
        self.logger.info("Starting")
        start = time.time()

        try:
            last_update = open(self.rootpath+"/last_update").read()
        except IOError:
            last_update = None

        current_timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        service = self.impersonate_user('https://www.googleapis.com/auth/calendar', 'calendar', 'v3')

        calendars = service.calendarList().list(minAccessRole='owner', maxResults=1000, showHidden=True).execute()
        total_entries = 0
        for calendar in calendars.get("items", []):
            page_token = None
            page_id = 0
            while True:
                events = service.events().list(calendarId=calendar.get("id"), timeMin='2000-01-01T00:00:01Z', updatedMin=last_update, maxAttendees=500, pageToken=page_token).execute()
                if len(events.get("items", [])) > 0:
                    json.dump(events.get("items"), open("%s/%s-%s-%s" % (self.rootpath, calendar.get("id"), current_timestamp, page_id), "w"))
                    total_entries += len(events.get("items"))
                page_token = events.get('nextPageToken')
                if not page_token:
                    break
                page_id += 1

        open(self.rootpath+"/last_update", "w").write(current_timestamp)
        end = time.time()
        elapsed = end - start
        self.logger.info("Finished in %.2f seconds. updateMin=%s, saved %s. Downloaded %s entries", elapsed, last_update, current_timestamp, total_entries)
        return total_entries

def main():
    users = get_users(DOMAIN)

    logger.info("Running with %s users", len(users))
    total_entries = 0
    for index, user in enumerate(users):
        if user in CALENDAR_IGNORE_USERS:
            logger.info("Skipping %s due to ignore list", user)
            continue
        logger.info("Status: %s/%s", index+1, len(users))
        calendarbackup = CalendarBackup(user)
        calendarbackup.initialize()
        total_entries += calendarbackup.run()
    logger.info("Finished downloading %s entries for %s users", total_entries, len(users))

if __name__ == '__main__':
    main()
