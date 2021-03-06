#Full Stack Nanodegree Project 4 - Connect 4 games. 

##Game Description:
This is an implementation of the classic Connect 4 game, where each player 
alternates dropping different colored chips (identified as 1's or 2's for our 
purposes) into a 7x7 veritical grid, where the user can only choose a column 
and the chip automatically falls to the lowest unoccupied space (represented 
by a 0) Each game begins with a all spaces empty, and user1 goes first, 
followed by user2, and alternating from there. 

The winner is the first player to get 4 chips in a row, either virtically, 
horizontally, or diagonally across the grid.  I'm alloting points based on the 
number of unnoccupied spaces at the end of the game, so that winning in less 
moves is rewarded more.  If there is no winner after a move, the message will 
be who's turn is up next.  If the game is won, turns are no longer allowed, and
the message congratulates the user name of the winner. 

Many different Connect 4 games can be played by many different Users at any
given time. Each game can be retrieved or played by using the path parameter
`urlsafe_game_key`.

##Files Included:
 - api.py: Contains endpoints and game playing logic.
 - app.yaml: App configuration.
 - cron.yaml: Cronjob configuration.
 - main.py: Handler for taskqueue handler.
 - models.py: Entity and message definitions including helper methods.
 - utils.py: Helper function for retrieving ndb.Models by urlsafe Key string.
 - Design.txt: A document describing the design and layout of the game, and 
 thought process behing it. 

##Endpoints Included:
 - **create_user**
    - Path: 'user'
    - Method: POST
    - Parameters: user_name, email (optional)
    - Returns: Message confirming creation of the User.
    - Description: Creates a new User. user_name provided must be unique. Will 
    raise a ConflictException if a User with that user_name already exists.
    
 - **new_game**
    - Path: 'game'
    - Method: POST
    - Parameters: user_1, user_2
    - Returns: GameForm with initial game state.
    - Description: Creates a new Game. The user names provided must be unique 
    and correspond to an existing user - will raise a NotFoundException if not.
     
 - **get_game**
    - Path: 'game/{urlsafe_game_key}'
    - Method: GET
    - Parameters: urlsafe_game_key
    - Returns: GameForm with current game state.
    - Description: Returns the current state of a game.

 - **get_game_history**
    - Path: 'game_history/{urlsafe_game_key}'
    - Method: GET
    - Parameters: urlsafe_game_key
    - Returns: HistoryForms of the current game
    - Description: Returns the current history of moves taken in the game.
    
 - **get_user_games**
    - Path: 'games/user/{user_name}'
    - Method: GET
    - Parameters: user_name
    - Returns: GameForms for the user's games
    - Description: Returns all active (not complete) games that include the 
    given user.

- **cancel_game**
    - Path: 'cancel/game/{urlsafe_game_key}'
    - Method: DELETE
    - Parameters: urlsafe_game_key
    - Returns: Message confirming cancelling of the game.
    - Description: Cancels and deletes the game
    
- **make_move**
    - Path: 'game/{urlsafe_game_key}'
    - Method: PUT
    - Parameters: urlsafe_game_key, user_name, column
    - Returns: GameForm with new game state.
    - Description: Accepts a column from the user and returns the updated state
    of the game. A history of the turn is logged on the game. If this causes a 
    game to end, a corresponding Score entity will be created.  If the user 
    isn't in the database, an exception stating such is returned.  If it is not 
    the given users turn, again an exception stating such is returned. If the 
    given column is not between 0 and 6, a BadRequestException is raised.  If the 
    column given is full, a ConflictException is raised. 
    
- **get_scores**
    - Path: 'scores'
    - Method: GET
    - Parameters: None
    - Returns: ScoreForms.
    - Description: Returns all Scores in the database (unordered).
    
- **get_user_scores**
    - Path: 'scores/user/{user_name}'
    - Method: GET
    - Parameters: user_name
    - Returns: ScoreForms. 
    - Description: Returns all Scores recorded by the provided player (unordered).
    Will raise a NotFoundException if the User does not exist.

- **get_user_rankings**
    - Path: 'rankings'
    - Method: GET
    - Parameters: max_number
    - Returns: UserRanks. 
    - Description: Returns the rankings of the users in order from most wins to
    least.  Optionally it takes a parameter max_number to limit the number of 
    rankings returned

##Models Included:
 - **User**
    - Stores unique user_name and (optional) email address.
    
 - **Game**
    - Stores unique game states. Associated with User model via KeyProperty.
    
 - **Score**
    - Records completed games. Associated with Users model via KeyProperty.

 - **Column**
    - A column of rows for the game.  Not its own database entity, included in
    Game.

 - **HistoricalRecord**
    - A recording a players turn and its result. Not its own database entity,
     included in Game.
    
##Forms Included:
 - **GameForm**
    - Representation of a Game's state (urlsafe_key, user1_name, user2_name,
    game_over flag, message, user_name).
 - **NewGameForm**
    - Used to create a new game (user1_name, user2_name)
 - **MakeMoveForm**
    - Inbound make move form (column, user_name).
 - **ScoreForm**
    - Representation of a completed game's Score (winner, loser, date, wonflag,
    points).
 - **ScoreForms**
    - Multiple ScoreForm container.
 - **StringMessage**
    - General purpose String container.
 - **HistoricalForm**
    - Representation of a move made in a game
 - **HistoricalForms**
    - Representation of all moves made in a game
 - **UserRank**
    - Number of wins and win percentage for a user
 - **UserRanks**
    - Sorted list of all UserRank, or the top number of players equal to 
    the option max_number
 