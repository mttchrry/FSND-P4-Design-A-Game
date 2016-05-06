# -*- coding: utf-8 -*-`
"""api.py - Create and configure the Game API exposing the resources.
This can also contain game logic. For more complex games it would be wise to
move game logic to another file. Ideally the API will be simple, concerned
primarily with communication to/from the API's users."""


import logging
import endpoints
from protorpc import remote, messages
from google.appengine.api import memcache
from google.appengine.api import taskqueue

from models import User, Game, Score
from models import StringMessage, NewGameForm, GameForm, MakeMoveForm,\
    ScoreForms
from utils import get_by_urlsafe

NEW_GAME_REQUEST = endpoints.ResourceContainer(NewGameForm)
GET_GAME_REQUEST = endpoints.ResourceContainer(
        urlsafe_game_key=messages.StringField(1),)
MAKE_MOVE_REQUEST = endpoints.ResourceContainer(
    MakeMoveForm,
    urlsafe_game_key=messages.StringField(1),)
USER_REQUEST = endpoints.ResourceContainer(user_name=messages.StringField(1),
                                           email=messages.StringField(2))

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
        return StringMessage(message='User {} created!'.format(
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
                    'A Users with those name do not exist!')
        try:
            game = Game.new_game(user1.key, user2.key, request.min,
                                 request.max, request.attempts)
        except ValueError:
            raise endpoints.BadRequestException('Maximum must be greater '
                                                'than minimum!')

        # Use a task queue to update the average attempts remaining.
        # This operation is not needed to complete the creation of a new game
        # so it is performed out of sequence.
        taskqueue.add(url='/tasks/cache_average_attempts')
        return game.to_form('Good luck playing Connect Four! Player {0} goes first'.format(user1.name))

    @endpoints.method(request_message=GET_GAME_REQUEST,
                      response_message=GameForm,
                      path='game/{urlsafe_game_key}',
                      name='get_game',
                      http_method='GET')
    def get_game(self, request):
        """Return the current game state."""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if game:
            return game.to_form('Time to make a move!')
        else:
            raise endpoints.NotFoundException('Game not found!')

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
                raise endpoints.NotFoundException(
                    'Not your turn')
        elif not game.player_1_turn and user.key != game.user2:
            if user.key != game.user1:
                raise endpoints.NotFoundException(
                    'User not in this game')
            else:
                raise endpoints.NotFoundException(
                    'Not your turn')

        # Make sure user picked a valid column.
        if request.column < 0 or request.column > 6:
            raise endpoints.NotFoundException(
                    'Must select a column between 0 and 6')

        # player 1 chip is 1, player 2 chip is 2.
        playerChip = 0
        if game.player_1_turn:
            playerChip = 1
        else:
            playerChip = 2

        logging.error(request.column)
        for idx, val in enumerate(game.gamegrid[request.column].row):
          if val == 0:
            game.gamegrid[request.column].row[idx] = playerChip
            break
          elif idx == 6:
            raise endpoints.NotFoundException(
                    'column is already full, pick another')
        if game.has_last_chip_won(request.column, endpoints):
            game.end_game(user.key, True)
            
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
        scores = Score.query(Score.user == user.key)
        return ScoreForms(items=[score.to_form() for score in scores])

    @endpoints.method(response_message=StringMessage,
                      path='games/average_attempts',
                      name='get_average_attempts_remaining',
                      http_method='GET')
    def get_average_attempts(self, request):
        """Get the cached average moves remaining"""
        return StringMessage(message=memcache.get(MEMCACHE_MOVES_REMAINING) or '')

    @staticmethod
    def _cache_average_attempts():
        """Populates memcache with the average moves remaining of Games"""
        games = Game.query(Game.game_over == False).fetch()
        if games:
            count = len(games)
            total_attempts_remaining = sum([game.attempts_remaining
                                        for game in games])
            average = float(total_attempts_remaining)/count
            memcache.set(MEMCACHE_MOVES_REMAINING,
                         'The average moves remaining is {:.2f}'.format(average))



api = endpoints.api_server([Connect4Api])
