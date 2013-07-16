"""
Google backup

Usage:
  backup.py gmail [--verbose] (all | <user>...)
  backup.py calendar [--verbose] (all | <user>...)
  backup.py drive [--verbose] (all | <user>...)
  backup.py full [--verbose] (all | <user>...)
  backup.py -h | --help

Options:
  -h --help     Show this screen.
  --verbose     More verbose output.

"""
from docopt import docopt
import sys

from calendarbackup import CalendarBackup
from gmailbackup import GmailBackup
from drivebackup import DriveBackup
from get_users import get_users
from settings import DOMAIN

SERVICES = ["gmail", "calendar", "drive"]

def main():
    """ Main method: parses command line arguments, fetch full list of users 
        and execute backups """
    run_services = []
    arguments = docopt(__doc__, version='Google Backup 0.1')
    if arguments["full"]:
        run_services.extend(SERVICES)
    else:
        for service in SERVICES:
            if arguments[service]:
                run_services.append(service)
    if len(run_services) == 0 or len(arguments["<user>"]) == 0:
        print __doc__
        return 1

    users = arguments["<user>"]
    if "all" in arguments["<user>"]:
        users = get_users(DOMAIN)

    for service in run_services:
        for user in users:
            backup = None
            if service == 'gmail':
                backup = GmailBackup(user)
            elif service == 'drive':
                backup = DriveBackup(user)
            elif service == 'calendar':
                backup = CalendarBackup(user)
            if backup:
                backup.initialize()
                backup.run()
    return 0

if __name__ == '__main__':
    sys.exit(main())
