Backup for Google services
==========================

Current status
--------------

This collection of programs is no longer maintained, and contains multiple bugs. This was in use around 2014, but many things have changed since.

Overview
--------


Backs up Gmail/Drive/Calendar. Uses domain wide authentication, so no authorization 
from Google Apps users is necessary. Emails are downloaded using modified offlineimap
and [XOAUTH2](https://developers.google.com/gmail/xoauth2_protocol).

Installation
------------

Google API authorization
------------------------

* Go to [Google API Console](https://code.google.com/apis/console/) 
* Create new project
* Open "Services" and enable "Admin SDK" (for downloading list of users), "Calendar API", "Drive API" and "Drive SDK".
* Open "API Access" and create new client ID. Select "Service account". Save the private key to program folder. Remember to protect the private key appropriately.
* Take note of the first client ID and email address.
* Create a second client ID for getting list of users from directory API. Select "Installed application", "Other".
* Download second "client_secrets.json" using "Download JSON" link. Put "client_secrets.json" to program folder.

Next, domain-wide authorization:

* Open [Google Admin Console](https://admin.google.com/)
* Go to "Advanced tools", "Manage third party OAuth Client access" (https://www.google.com/a/cpanel/yourdomain.tld/ManageOauthClients). [More information.](http://support.google.com/a/bin/answer.py?hl=en&answer=162105)
* Paste the first client ID to "Client Name" and "https://mail.google.com/,https://www.googleapis.com/auth/calendar,https://www.googleapis.com/auth/drive.readonly" to API scopes. Click "Authorize"

On the first run, authorization URL is printed out. Open the URL with admin user, check that only readonly access to your user list is required and click "Authorize". Copy authentication token and paste it back to the terminal.

Dependencies and settings
-------------------------

* pip install -r requirements.txt
* Move settings.py.sample to settings.py. Modify it with values obtained above from API console.

System Requirements
-------------------------
* Currently hardcoded to use zfs utility
* Requires [OfflineIMAP](http://offlineimap.org/) for email sync

