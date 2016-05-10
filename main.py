#!/usr/bin/env python

"""main.py - This file contains handlers that are called by taskqueue and/or
cronjobs."""
import logging

import webapp2
from google.appengine.api import mail, app_identity
from api import Connect4Api
from google.appengine.ext import ndb

from models import User, Game


class SendReminderEmail(webapp2.RequestHandler):

    def get(self):
        """Send a reminder email to each User with an email about games.
        Called every hour using a cron job"""
        app_id = app_identity.get_application_id()
        users = User.query(User.email != None)
        for user in users:
            gamesOpen = Game.query(ndb.AND(ndb.OR(Game.user1 == user.key,
                                                  Game.user2 == user.key),
                                           Game.game_over == False))
            if gamesOpen.count() > 0:
                subject = 'This is a reminder!'
                body = 'Hello {}.  Finish up your open Connect Four \
                games!'.format(user.name)
                # This will send test emails, the arguments to send_mail are:
                # from, to, subject, body
                mail.send_mail('noreply@{}.appspotmail.com'.format(app_id),
                               user.email,
                               subject,
                               body)

app = webapp2.WSGIApplication([
    ('/crons/send_reminder', SendReminderEmail)
], debug=True)
