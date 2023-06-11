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

PLAYER_SYMBOL = 'X'
OPPONENT_SYMBOL = 'O'


def is_opponents_turn():
    print('Is opponents turn')
    random_num = random.random()
    if random_num < 0.5:
        return True


def opponents_move():
    print('Opponents move')
    emit('state_updated', {'message': 'Opponent\'s move'})
    time.sleep(2)
    empty_field_ids = [index for index, value in enumerate(session['board']) if value == '']
    chosen_id = random.choice(empty_field_ids)
    session['board'][chosen_id] = OPPONENT_SYMBOL

    if is_winner():
        session['losses'] += 1
        if 0 < session['credits'] < 3:
            session['time'] = time.time() - session['time']
            print(session['time'])
            print(f"Stats: {session['wins']}W {session['draws']}D {session['losses']}L")
            emit('game_ended', {'board': session['board'], 'message': 'Opponent won. Game over!', 'credits': session['credits']})
        else:
            emit('round_ended', {'board': session['board'], 'message': 'Opponent won', 'credits': session['credits']})
    elif is_draw():
        session['draws'] += 1
        if 0 < session['credits'] < 3:
            session['time'] = time.time() - session['time']
            print(session['time'])
            print(f"Stats: {session['wins']}W {session['draws']}D {session['losses']}L")
            emit('game_ended', {'board': session['board'], 'message': 'It\'s a draw. Game over!', 'credits': session['credits']})
        else:
            emit('round_ended', {'board': session['board'], 'message': 'It\'s a draw', 'credits': session['credits']})
    else:
        emit('state_updated', {'board': session['board'], 'message': 'Your move', 'unlock': True})


def game_init():
    print('Game init')
    session['credits'] -= 3
    session['board'] = ['' for _ in range(9)]
    emit('game_started', {'message': 'Game has started', 'credits': session['credits'], 'board': session['board']})

    if is_opponents_turn():
        opponents_move()
    else:
        emit('state_updated', {'board': session['board'], 'message': 'Your move', 'unlock': True})


def is_winner():
    print('Winner check')
    for x in range(0, 9, 3):
        if session['board'][x] != '' and session['board'][x] == session['board'][x+1] == session['board'][x+2]:
            return True

    for x in range(3):
        if session['board'][x] != '' and session['board'][x] == session['board'][x+3] == session['board'][x+6]:
            return True

    if session['board'][0] != '' and session['board'][0] == session['board'][4] == session['board'][8]:
        return True

    if session['board'][2] != '' and session['board'][2] == session['board'][4] == session['board'][6]:
        return True


def is_draw():
    print('Draw check')
    if all(value != "" for value in session['board']):
        return True


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
    print('Handle start game')
    session['credits'] = 10
    session['wins'] = 0
    session['draws'] = 0
    session['losses'] = 0
    session['time'] = time.time()
    game_init()


@socketio.on('play_again')
def handle_play_again():
    print('Handle play again')
    if session['credits'] == 0:
        emit('state_updated', {'message': 'Add more credits to continue playing'})
    elif 0 < session['credits'] < 3:
        emit('state_updated', {'message': 'Insufficient credits to start another game'})
    else:
        emit('playing_again', {'message': 'Another game has started', 'credits': session['credits'], 'board': session['board']})
        game_init()


@socketio.on('add_credits')
def handle_add_credits():
    print('Handle add credits')
    if session['credits'] == 0:
        session['credits'] += 10
        emit('state_updated', {'message': 'Extra credits have been added', 'credits': session['credits']})
    else:
        emit('state_updated', {'message': 'You cannot add more credits'})


@socketio.on('validate_move')
def handle_validate_move(box_id):
    print('Handle validate move')
    box_id = int(box_id)
    if session['board'][box_id] == '':
        session['board'][box_id] = PLAYER_SYMBOL

        emit('state_updated', {'board': session['board']})

        if is_winner():
            session['wins'] += 1
            session['credits'] += 4
            emit('round_ended', {'board': session['board'], 'message': 'You won', 'credits': session['credits']})
        elif is_draw():
            session['draws'] += 1
            if 0 < session['credits'] < 3:
                session['time'] = time.time() - session['time']
                print(session['time'])
                print(f"Stats: {session['wins']}W {session['draws']}D {session['losses']}L")
                emit('game_ended', {'board': session['board'], 'message': 'It\'s a draw. Game over!', 'credits': session['credits']})
            else:
                emit('round_ended', {'board': session['board'], 'message': 'It\'s a draw', 'credits': session['credits']})
        else:
            opponents_move()

    else:
        emit('state_updated', {'message': 'Wrong move, try another field', 'unlock': True})


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
