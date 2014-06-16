
# Beeminder and Notmuch mail

This is a little script that can periodically report statistics about your [Notmuch](http://notmuchmail.org/) mail archive to [Beeminder](https://www.beeminder.com/). It can report either a count of the number of messages matching a search, or the age (in days) of the oldest message matching a search. For example:

````
./beeminder_notmuch.py count my-goal-name tag:inbox
./beeminder_notmuch.py age   another-goal tag:waiting
````

To configure, you should [log in to beeminder](https://www.beeminder.com/users/sign_in) and then visit the [auth_token API link](https://www.beeminder.com/api/v1/auth_token.json). You should see a page something like this:

````
{"username":"myname","auth_token":"to9jai7yohqu4ce4fae6"}
````

Copy those credentials and paste them into a file called `.beeminder.auth` in your home directory.

You can now experiment with the `./beeminder_notmuch.py` script and different search queries. Once satisfied, you probably want to ask `cron` to run the reports periodically, using `crontab -e`

Here is my crontab, which runs these about every two hours.

````
14 */2 * * * /home/league/p/beeminder-notmuchmail/beeminder_notmuch.py count notmuch tag:inbox not tag:bulk
13 */2 * * * /home/league/p/beeminder-notmuchmail/beeminder_notmuch.py age notmuch-age tag:inbox not tag:bulk
````

I suppose I'll also let you peek at my Beeminder pages for these, so you can tell how I'm doing:

 - [inbox count goal](https://www.beeminder.com/league/notmuch/)
 - [inbox age goal](https://www.beeminder.com/league/goals/notmuch-age)
