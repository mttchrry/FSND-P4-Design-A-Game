# -*- coding: utf-8 -*-`
"""api.py - Create and configure the Game API exposing the resources.
This can also contain game logic. For more complex games it would be wise to
move game logic to another file. Ideally the API will be simple, concerned
primarily with communication to/from the API's users."""


import endpoints
from protorpc import remote, messages
from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from models import User, Game, Score
from models import StringMessage, NewGameForm, GameForm, MakeMoveForm,\
    ScoreForms, GameForms, UserRank, UserRanks, HistoricalRecord, \
    HistoryForms
from utils import get_by_urlsafe

NEW_GAME_REQUEST = endpoints.ResourceContainer(NewGameForm)
GET_GAME_REQUEST = endpoints.ResourceContainer(
    urlsafe_game_key=messages.StringField(1),)
GET_USER_GAMES_REQUEST = endpoints.ResourceContainer(
    user_name=messages.StringField(1))
MAKE_MOVE_REQUEST = endpoints.ResourceContainer(
    MakeMoveForm,
    urlsafe_game_key=messages.StringField(1),)
USER_REQUEST = endpoints.ResourceContainer(user_name=messages.StringField(1),
                                           email=messages.StringField(2))
USER_RANKINGS = endpoints.ResourceContainer(
    max_number=messages.IntegerField(1))

MEMCACHE_MOVES_REMAINING = 'MOVES_REMAINING'


@endpoints.api(name='connect_four', version='v1')
class Connect4Api(remote.Service):

    """Game API"""
    @endpoints.method(request_message=USER_REQUEST,
                      response_message=StringMessage,
                      path='user',
                      name='create_user',
                      http_method='POST')
    def create_user(self, request):
        """Create a User. Requires a unique username"""
        if User.query(User.name == request.user_name).get():
            raise endpoints.ConflictException(
                'A User with that name already exists!')
        user = User(name=request.user_name, email=request.email)
        user.put()
        return StringMessage(message='User {} created.'.format(
            request.user_name))

    @endpoints.method(request_message=NEW_GAME_REQUEST,
                      response_message=GameForm,
                      path='game',
                      name='new_game',
                      http_method='POST')
    def new_game(self, request):
        """Creates new game"""
        user1 = User.query(User.name == request.user_1).get()
        user2 = User.query(User.name == request.user_2).get()
        if not user1 or not user2:
            raise endpoints.NotFoundException(
                'A Users with those names do not exist!')
        try:
            game = Game.new_game(user1.key, user2.key)
        except ValueError:
            raise endpoints.BadRequestException('User cannot play himself.')

        # Use a task queue to update the average attempts remaining.
        # This operation is not needed to complete the creation of a new game
        # so it is performed out of sequence.
        taskqueue.add(url='/tasks/cache_average_attempts')
        return game.to_form('Good luck playing Connect Four! Player {0} \
        goes first'.format(user1.name))

    @endpoints.method(request_message=GET_GAME_REQUEST,
                      response_message=GameForm,
                      path='game/{urlsafe_game_key}',
                      name='get_game',
                      http_method='GET')
    def get_game(self, request):
        """Return the current game state."""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if game:
            return game.to_form('Time to make a move.')
        else:
            raise endpoints.NotFoundException('Game not found.')

    @endpoints.method(request_message=GET_GAME_REQUEST,
                      response_message=HistoryForms,
                      path='game_history/{urlsafe_game_key}',
                      name='get_game_history',
                      http_method='GET')
    def get_game_history(self, request):
        """Return the current game state."""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if game:
            return HistoryForms(
                items=[history.to_form() for history in game.game_history])
        else:
            raise endpoints.NotFoundException('Game History not found.')

    @endpoints.method(request_message=GET_USER_GAMES_REQUEST,
                      response_message=GameForms,
                      path='games/user/{user_name}',
                      name='get_user_games',
                      http_method='GET')
    def get_user_games(self, request):
        """Get the users remaining open games"""
        user = User.query(User.name == request.user_name).get()
        if not user:
            raise endpoints.NotFoundException(
                'A Users with those name do not exist.')
        games_left = Game.query(ndb.AND(ndb.OR(Game.user1 == user.key,
                                              Game.user2 == user.key),
                                       Game.game_over == False))
        return GameForms(
            items=[game.to_form("Open Game") for game in games_left])

    @endpoints.method(request_message=GET_GAME_REQUEST,
                      response_message=StringMessage,
                      path='cancel/game/{urlsafe_game_key}',
                      name='cancel_game',
                      http_method='DELETE')
    def cancel_game(self, request):
        """Cancel the current game state."""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if game:
            if game.game_over:
                raise endpoints.UnauthorizedException(
                    "Can't cancel completed game")
            else:
                game.key.delete()
                return StringMessage(message='Game {} canceled and deleted.'.
                                     format(request.urlsafe_game_key))
        else:
            raise endpoints.NotFoundException('Game not found.')

    @endpoints.method(request_message=MAKE_MOVE_REQUEST,
                      response_message=GameForm,
                      path='game/{urlsafe_game_key}',
                      name='make_move',
                      http_method='PUT')
    def make_move(self, request):
        """Makes a move. Returns a game state with message"""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if game.game_over:
            return game.to_form('Game already over!')

        user = User.query(User.name == request.user).get()
        if not user:
            raise endpoints.NotFoundException(
                'A Users with those name do not exist!')

        # handle all incorrect turn attempts or users not in the game
        if game.player_1_turn and user.key != game.user1:
            if user.key != game.user2:
                raise endpoints.NotFoundException(
                    'User not in this game')
            else:
                raise endpoints.ConflictException(
                    'Not your turn')
        elif not game.player_1_turn and user.key != game.user2:
            if user.key != game.user1:
                raise endpoints.NotFoundException(
                    'User not in this game')
            else:
                raise endpoints.ConflictException(
                    'Not your turn')

        # Make sure user picked a valid column.
        if request.column < 0 or request.column > 6:
            raise endpoints.BadRequestException(
                'Must select a column between 0 and 6')

        # player 1 chip is 1, player 2 chip is 2.
        player_chip = 1 if game.player_1_turn else 2

        for idx, val in enumerate(game.gamegrid[request.column].row):
            # replace the lowest unoccupied space(indicated by a 0) 
            # with the current chip.
            if val == 0:
                game.gamegrid[request.column].row[idx] = player_chip
                break
            elif idx == 6:
                raise endpoints.ConflictException(
                    'column is already full, pick another')

        if game.has_last_chip_won(request.column, endpoints):
            # Player just won, end game accordingly
            history = HistoricalRecord(
                player_name=user.name, column=request.column,
                game_state="Just Won!")
            game.game_history.append(history)
            game.end_game(user.key, True)
            msg = "Player {0} just won!".format(user.name)
        elif game.spaces_left() == 0:
            # there are no open spaces, tie game
            history = HistoricalRecord(
                player_name=user.name, column=request.column,
                game_state="Tie Game")
            game.game_history.append(history)
            game.end_game()
            msg = "Game over, all spaces filled.  There are no winners here."
        else:
            # normal turn, next players turn. 
            history = HistoricalRecord(
                player_name=user.name, column=request.column,
                game_state="Next player's turn")
            game.game_history.append(history)
            game.player_1_turn = not game.player_1_turn
            if game.player_1_turn:
                msg = 'Player {0} is up next'.format(game.user1.get().name)
            else:
                msg = 'Player {0} is up next'.format(game.user2.get().name)

        game.put()
        return game.to_form(msg)

    @endpoints.method(response_message=ScoreForms,
                      path='scores',
                      name='get_scores',
                      http_method='GET')
    def get_scores(self, request):
        """Return all scores"""
        return ScoreForms(items=[score.to_form() for score in Score.query()])

    @endpoints.method(request_message=USER_REQUEST,
                      response_message=ScoreForms,
                      path='scores/user/{user_name}',
                      name='get_user_scores',
                      http_method='GET')
    def get_user_scores(self, request):
        """Returns all of an individual User's scores"""
        user = User.query(User.name == request.user_name).get()
        if not user:
            raise endpoints.NotFoundException(
                'A User with that name does not exist!')
        scores = Score.query(
            ndb.OR(Score.loser == user.key, Score.winner == user.key))
        return ScoreForms(items=[score.to_form() for score in scores])

    @endpoints.method(request_message=USER_RANKINGS,
                      response_message=UserRanks,
                      path='rankings',
                      name='get_user_rankings',
                      http_method='GET')
    def get_user_rankings(self, request):
        """Returns the user rankings, sorted by highest first, up to number
         indicated"""
        users = User.query()
        rankings = []
        for user in users:
            total_scores = Score.query(
                ndb.OR(Score.loser == user.key, Score.winner == user.key))
            winning_scores = Score.query(
                ndb.AND(Score.winner == user.key, Score.won == True))
            win_p = 0.0
            if total_scores.count() > 0:
                win_p = winning_scores.count()/float(total_scores.count())
            userRank = UserRank(
                user_name=user.name, wins=winning_scores.count(),
                win_percent=win_p)
            rankings.append(userRank)
        sorted(rankings, key=lambda UserRank: UserRank.wins, reverse=True)
        if request.max_number != None:
            rankings = rankings[0:request.max_number]
        return UserRanks(items=rankings)


api = endpoints.api_server([Connect4Api])
