import random
import time
import uuid
from datetime import datetime, date, timedelta
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
    random_num = random.random()
    if random_num < 0.5:
        return True


def save_session_data_to_db():
    session_data = GameStats(player_id=session['player_id'],
                             wins=session['wins'],
                             draws=session['draws'],
                             losses=session['losses'],
                             games_length=timedelta(seconds=session['time']))
    db.session.add(session_data)
    db.session.commit()


def opponents_move():
    emit('state_updated', {'message': 'Opponent\'s move'})
    time.sleep(1.5)
    empty_field_ids = [index for index, value in enumerate(session['board']) if value == '']
    chosen_id = random.choice(empty_field_ids)
    session['board'][chosen_id] = OPPONENT_SYMBOL

    if is_winner():
        session['losses'] += 1
        if 0 < session['credits'] < 3:
            session['time'] = time.time() - session['time']
            save_session_data_to_db()
            emit('game_ended', {'board': session['board'], 'message': 'Opponent won. Game over!', 'credits': session['credits']})
        else:
            emit('round_ended', {'board': session['board'], 'message': 'Opponent won', 'credits': session['credits']})
    elif is_draw():
        session['draws'] += 1
        if 0 < session['credits'] < 3:
            session['time'] = time.time() - session['time']
            save_session_data_to_db()
            emit('game_ended', {'board': session['board'], 'message': 'It\'s a draw. Game over!', 'credits': session['credits']})
        else:
            emit('round_ended', {'board': session['board'], 'message': 'It\'s a draw', 'credits': session['credits']})
    else:
        emit('state_updated', {'board': session['board'], 'message': 'Your move', 'unlock': True})


def game_init():
    session['credits'] -= 3
    session['board'] = ['' for _ in range(9)]
    emit('game_started', {'message': 'Game has started', 'credits': session['credits'], 'board': session['board']})

    if is_opponents_turn():
        opponents_move()
    else:
        emit('state_updated', {'board': session['board'], 'message': 'Your move', 'unlock': True})


def is_winner():
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
    if all(value != "" for value in session['board']):
        return True


@socketio.on('connect')
def handle_connect():
    print('Client connected')
    session['player_id'] = str(uuid.uuid4())
    emit('connected', {'player_id': session['player_id']})


@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')


@socketio.on('start_game')
def handle_start_game():
    session['credits'] = 10
    session['wins'] = 0
    session['draws'] = 0
    session['losses'] = 0
    session['time'] = time.time()
    game_init()


@socketio.on('play_again')
def handle_play_again():
    if session['credits'] == 0:
        emit('state_updated', {'message': 'Add more credits to continue playing'})
    elif 0 < session['credits'] < 3:
        emit('state_updated', {'message': 'Insufficient credits to start another game'})
    else:
        emit('playing_again', {'message': 'Another game has started', 'credits': session['credits'], 'board': session['board']})
        game_init()


@socketio.on('add_credits')
def handle_add_credits():
    if session['credits'] == 0:
        session['credits'] += 10
        emit('state_updated', {'message': 'Extra credits have been added', 'credits': session['credits']})
    else:
        emit('state_updated', {'message': 'You cannot add more credits'})


@socketio.on('validate_move')
def handle_validate_move(box_id):
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
                save_session_data_to_db()
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
def view_stats():
    current_date = date.today()
    start_of_day = datetime.combine(current_date, datetime.min.time())
    end_of_day = datetime.combine(current_date, datetime.max.time())

    total_wins = db.session.query(db.func.sum(GameStats.wins)).filter(GameStats.timestamp.between(start_of_day, end_of_day)).scalar()
    total_losses = db.session.query(db.func.sum(GameStats.losses)).filter(GameStats.timestamp.between(start_of_day, end_of_day)).scalar()
    total_draws = db.session.query(db.func.sum(GameStats.draws)).filter(GameStats.timestamp.between(start_of_day, end_of_day)).scalar()
    total_time = db.session.query(db.func.sum(GameStats.games_length)).filter(GameStats.timestamp.between(start_of_day, end_of_day)).scalar()

    if total_time:
        total_seconds = total_time.total_seconds()
        rounded_seconds = round(total_seconds)
        rounded_delta = timedelta(seconds=rounded_seconds)
        total_time = str(rounded_delta)
    else:
        total_time = '0:00:00'

    data_out = jsonify({
        'total_wins': total_wins if total_wins else 0,
        'total_draws': total_draws if total_draws else 0,
        'total_losses': total_losses if total_losses else 0,
        'total_seconds': total_time,
    })

    return data_out


if __name__ == '__main__':
    from models import GameStats
    with app.app_context():
        db.create_all()
    socketio.run(app, allow_unsafe_werkzeug=True)
