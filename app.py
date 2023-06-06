import random
import time
import uuid
from creds import db_username, db_password, db_host, db_name, app_secret_key
from flask import Flask, jsonify, render_template, session
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{db_username}:{db_password}@{db_host}/{db_name}'
app.secret_key = app_secret_key
db = SQLAlchemy(app)
socketio = SocketIO(app)


def determine_starting_player():
    random_num = random.random()
    if random_num < 0.5:
        return 'X'
    return 'O'


def opponent_move():
    empty_field_ids = [index for index, value in enumerate(session['board']) if value == '']
    return random.choice(empty_field_ids)


def game_reset():
    session['board'] = ['' for _ in range(9)]
    session['winner_fields'] = None
    session['winner'] = None


def game_over_check():
    for x in range(0, 9, 3):
        if session['board'][x] != '' and session['board'][x] == session['board'][x+1] == session['board'][x+2]:
            session['winner'] = session['board'][x]
            session['winner_fields'] = x, x+1, x+2

    for x in range(3):
        if session['board'][x] != '' and session['board'][x] == session['board'][x+3] == session['board'][x+6]:
            session['winner'] = session['board'][x]
            session['winner_fields'] = x, x+3, x+6

    if session['board'][0] != '' and session['board'][0] == session['board'][4] == session['board'][8]:
        session['winner'] = session['board'][0]
        session['winner_fields'] = 0, 4, 7

    if session['board'][2] != '' and session['board'][2] == session['board'][4] == session['board'][6]:
        session['winner'] = session['board'][2]
        session['winner_fields'] = 2, 4, 6


@socketio.on('connect')
def handle_connect():
    print('Client connected')
    session['player_id'] = str(uuid.uuid4())
    session['credits'] = 10
    emit('connected', {'player_id': session['player_id'], 'credits': session['credits']})


@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')


@socketio.on('start_game')
def handle_start_game():
    print('Game started')
    session['credits'] -= 3

    game_reset()

    session['turn'] = determine_starting_player()
    if session['turn'] == 'O':
        chosen_field_id = opponent_move()
        session['board'][chosen_field_id] = 'O'
        session['turn'] = 'X'

    emit('game_started', {'message': 'Game has started',
                          'credits': session['credits'],
                          'board': session['board'],
                          'turn': session['turn']})


@socketio.on('play_again')
def handle_play_again():
    if session['credits'] == 0:
        emit('action_failed', {'message': 'Add more credits to continue playing'})
    elif 0 < session['credits'] < 3:
        emit('action_failed', {'message': 'Insufficient credits to start another game'})
    else:
        session['credits'] -= 3
        game_reset()
        emit('playing_again', {'message': 'Another game has started', 'credits': session['credits']})


@socketio.on('add_credits')
def handle_add_credits():
    if 0 < session['credits'] < 3:
        session['credits'] += 10
        emit('credits_added', {'message': 'Credits has been added', 'credits': session['credits']})
    else:
        emit('action_failed', {'message': 'You cannot add more credits'})


@socketio.on('validate_move')
def handle_validate_move(box_id, turn):
    print('Validating move:', box_id, turn)
    box_id = int(box_id)
    if session['board'][box_id] == '':
        session['board'][box_id] = turn

        game_over_check()

        emit('move_validated', {'box_id': box_id,
                                'winner_fields': session['winner_fields'],
                                'winner': session['winner']})
    else:
        emit('action_failed', {'message': 'Wrong move, try another field'})


@socketio.on('opponent_move')
def handle_opponent_move():
    time.sleep(2)
    chosen_field_id = opponent_move()
    session['board'][chosen_field_id] = 'O'
    session['turn'] = 'X'
    emit('opponent_moved', {'turn': session['turn'], 'id': chosen_field_id})


@socketio.on('round_win')
def handle_round_win():
    session['credits'] += 4
    emit('round_won', {'message': 'You won!', 'credits': session['credits']})


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/stats', methods=['GET'])
def view_statistics():
    total_wins = db.session.query(db.func.sum(GameStats.wins)).scalar()
    total_loses = db.session.query(db.func.sum(GameStats.loses)).scalar()
    total_draws = db.session.query(db.func.sum(GameStats.draws)).scalar()
    games_played = db.session.query(db.func.sum(GameStats.games_played)).scalar()
    games_length = db.session.query(db.func.sum(GameStats.games_length)).scalar()

    return jsonify({
        'total_wins': total_wins,
        'total_loses': total_loses,
        'total_draws': total_draws,
        'games_played': games_played,
        'games_length': games_length,
    })


if __name__ == '__main__':
    from models import GameStats
    socketio.run(app, allow_unsafe_werkzeug=True)
