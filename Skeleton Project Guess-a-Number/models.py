"""models.py - This file contains the class definitions for the Datastore
entities used by the Game. Because these classes are also regular Python
classes they can include methods (such as 'to_form' and 'new_game')."""

import logging
import random
from datetime import date
from protorpc import messages
from google.appengine.ext import ndb


class User(ndb.Model):

    """User profile"""
    name = ndb.StringProperty(required=True)
    email = ndb.StringProperty()


class Column(ndb.Model):
    row = ndb.IntegerProperty(repeated=True)


class HistoricalRecord(ndb.Model):
    player_name = ndb.StringProperty(required=True)
    column = ndb.IntegerProperty(required=True)
    game_state = ndb.StringProperty(required=True)

    def to_form(self):
        form = HistoryForm()
        form.player_name = self.player_name
        form.game_state = self.game_state
        form.column = self.column
        return form


class Game(ndb.Model):

    """Game object"""
    gamegrid = ndb.LocalStructuredProperty(Column, repeated=True)
    game_score = ndb.IntegerProperty(required=True, default=0)
    game_winner = ndb.KeyProperty(kind='User')
    game_over = ndb.BooleanProperty(required=True, default=False)
    user1 = ndb.KeyProperty(required=True, kind='User')
    user2 = ndb.KeyProperty(required=True, kind='User')
    player_1_turn = ndb.BooleanProperty(required=True, default=True)
    game_history = ndb.LocalStructuredProperty(HistoricalRecord, repeated=True)

    @classmethod
    def new_game(cls, user1, user2):
        """Creates and returns a new game"""
        emptyColumn = Column(row=[0, 0, 0, 0, 0, 0, 0])
        grid = [emptyColumn,
                emptyColumn,
                emptyColumn,
                emptyColumn,
                emptyColumn,
                emptyColumn,
                emptyColumn]
        game = Game(user1=user1,
                    user2=user2,
                    gamegrid=grid,
                    game_over=False)
        game.put()
        return game

    def to_form(self, message):
        """Returns a GameForm representation of the Game"""
        form = GameForm()
        form.urlsafe_key = self.key.urlsafe()
        form.user1_name = self.user1.get().name
        form.user2_name = self.user2.get().name
        form.game_over = self.game_over
        form.message = message
        index = 0
        columnString = "grid_column"
        for aColumn in self.gamegrid:
            currentColumn = columnString + str(index)
            columnField = form.field_by_name(currentColumn)
            listcolumn = []
            for row in aColumn.row:
                listcolumn.append(row)
            setattr(form, columnField.name, listcolumn)
            # logging.warning(listcolumn)
            index += 1
        if self.game_winner != None:
            form.game_winner = self.game_winner.get().name
        return form

    def end_game(self, winner=None, won=False):
        """Ends the game - if won is True, the player won. - if won is False,
        the player lost."""
        self.game_over = True
        self.game_winner = winner
        loser = self.user1
        if loser == winner:
            loser = self.user2
        self.put()
        # Add the game to the score 'board'
        points = self.spaces_left()
        score = Score(winner=winner, loser=loser, date=date.today(), won=won,
                      points=points)
        score.put()

    def has_last_chip_won(self, column, endpoints):
        lastUsedIndex = 0
        chipval = 0
        # get the last chip put in the column
        for idx, chipval in enumerate(self.gamegrid[column].row):

            if chipval == 0:
                if idx == 0:
                    raise endpoints.NotFoundException(
                        'no chip in this column, could not have been winner 1')
                lastUsedIndex = idx - 1
                break
            if idx == 6:
                lastUsedIndex = 6

        chipval = self.gamegrid[column].row[lastUsedIndex]
        # if the last chip isn't the current players turn, we have a problem.
        if self.player_1_turn and chipval != 1:
            raise endpoints.NotFoundException(
                'Wrong chip on this column, could not have been winner 2')
        elif not self.player_1_turn and chipval != 2:
            raise endpoints.NotFoundException(
                'Wrong chip on this column, could not have been winner 3')

        # Check for 3 more in the -45 degree direction
        if self.check_win_direction(column, lastUsedIndex, -1, 1, 3, chipval):
            return True

        # Check for 3 more in the horizontal
        if self.check_win_direction(column, lastUsedIndex, -1, 0, 3, chipval):
            return True

        # Check for 3 more to the 45 degree direction
        if self.check_win_direction(column, lastUsedIndex, -1, -1, 3, chipval):
            return True

        # Check for 3 more vertically
        if self.check_win_direction(column, lastUsedIndex, 0, -1, 3, chipval):
            return True

    def check_win_direction(self, x, y, dx, dy, numberLeft, player,
                            alreadyreversed=False):
        #logging.error(str(x)+ '_'+str(dx) +',' + str(y)+'_'+str(dy)+', '+str(numberLeft)+ '_'+str(player) + 'A? '+ str(alreadyreversed))
        if x+dx < 0 or x + dx > 6 or y+dy < 0 or y + dy > 6:
            return False
        if self.gamegrid[x + dx].row[y+dy] == player:
            if numberLeft == 1:
                return True
            else:
                numberLeft -= 1
                return self.check_win_direction(
                    x+dx, y+dy, dx, dy, numberLeft, player, alreadyreversed)
        elif alreadyreversed == False:
            alreadyreversed = True
            numberGone = 3-numberLeft
            return self.check_win_direction(x-(dx*numberGone),
                                            y-(dy*numberGone), -dx, 
                                            -dy, numberLeft, player,
                                            alreadyreversed)
        else:
            return False

    def spaces_left(self):
        # score is the total number of chips not used in the game.
        score = 0
        for aColumn in self.gamegrid:
            for item in aColumn.row:
                if item == 0:
                    score += 1
        return score


class Score(ndb.Model):

    """Score object"""
    winner = ndb.KeyProperty(required=True, kind='User')
    loser = ndb.KeyProperty(required=True, kind='User')
    date = ndb.DateProperty(required=True)
    won = ndb.BooleanProperty(required=True)
    points = ndb.IntegerProperty(required=True)

    def to_form(self):
        return ScoreForm(winner_name=self.winner.get().name,
                         loser_name=self.loser.get().name, won=self.won,
                         date=str(self.date), points=self.points)


class GameForm(messages.Message):

    """GameForm for outbound game state information"""
    urlsafe_key = messages.StringField(1, required=True)
    game_over = messages.BooleanField(3, required=True)
    message = messages.StringField(4, required=True)
    user1_name = messages.StringField(5, required=True)
    grid_column0 = messages.IntegerField(6, repeated=True)
    grid_column1 = messages.IntegerField(7, repeated=True)
    grid_column2 = messages.IntegerField(8, repeated=True)
    grid_column3 = messages.IntegerField(9, repeated=True)
    grid_column4 = messages.IntegerField(10, repeated=True)
    grid_column5 = messages.IntegerField(11, repeated=True)
    grid_column6 = messages.IntegerField(12, repeated=True)
    user2_name = messages.StringField(13, required=True)
    game_winner = messages.StringField(14, required=False)


class GameForms(messages.Message):

    """Return multiple GameForms"""
    items = messages.MessageField(GameForm, 1, repeated=True)


class NewGameForm(messages.Message):

    """Used to create a new game"""
    user_1 = messages.StringField(1, required=True)
    user_2 = messages.StringField(2, required=True)


class MakeMoveForm(messages.Message):

    """Used to make a move in an existing game"""
    user = messages.StringField(1, required=True)
    column = messages.IntegerField(2, required=True)


class ScoreForm(messages.Message):

    """ScoreForm for outbound Score information"""
    winner_name = messages.StringField(1, required=True)
    loser_name = messages.StringField(2, required=True)
    date = messages.StringField(3, required=True)
    won = messages.BooleanField(4, required=True)
    points = messages.IntegerField(5, required=True)


class ScoreForms(messages.Message):

    """Return multiple ScoreForms"""
    items = messages.MessageField(ScoreForm, 1, repeated=True)


class HistoryForm(messages.Message):
    player_name = messages.StringField(1, required=True)
    game_state = messages.StringField(2, required=True)
    column = messages.IntegerField(3, required=True)


class HistoryForms(messages.Message):

    """Return multiple GameForms"""
    items = messages.MessageField(HistoryForm, 1, repeated=True)


class UserRank(messages.Message):
    user_name = messages.StringField(1, required=True)
    wins = messages.IntegerField(3, required=True)
    win_percent = messages.FloatField(4, required=True)


class UserRanks(messages.Message):
    items = messages.MessageField(UserRank, 1, repeated=True)


class StringMessage(messages.Message):

    """StringMessage-- outbound (single) string message"""
    message = messages.StringField(1, required=True)
