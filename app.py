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
AI_DEPTH_LEVEL = 3


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


def get_available_positions():
    return [i for i, value in enumerate(session['board']) if value == '']


def make_ai_move():
    return make_minimax_move(depth=AI_DEPTH_LEVEL)


def evaluate_score():
    if is_winner(OPPONENT_SYMBOL):
        return 1
    elif is_winner(PLAYER_SYMBOL):
        return -1
    else:
        return 0


def minimax(depth, is_maximizing):
    if depth == 0 or is_winner(PLAYER_SYMBOL) or is_winner(OPPONENT_SYMBOL):
        return evaluate_score()

    if is_maximizing:
        best_score = float('-inf')
        for position in get_available_positions():
            session['board'][position] = OPPONENT_SYMBOL
            score = minimax(depth - 1, False)
            session['board'][position] = ''
            best_score = max(score, best_score)
        return best_score
    else:
        best_score = float('inf')
        for position in get_available_positions():
            session['board'][position] = PLAYER_SYMBOL
            score = minimax(depth - 1, True)
            session['board'][position] = ''
            best_score = min(score, best_score)
        return best_score


def make_minimax_move(depth):
    best_score = float('-inf')
    best_move = None
    available_positions = get_available_positions()
    for position in available_positions:
        session['board'][position] = OPPONENT_SYMBOL
        score = minimax(depth - 1, False)
        session['board'][position] = ''
        if score > best_score:
            best_score = score
            best_move = position

    if best_move is None:
        if available_positions:
            best_move = random.choice(available_positions)

    return best_move


def opponents_move():
    emit('state_updated', {'message': 'Opponent\'s move'})
    time.sleep(1.5)
    chosen_id = make_ai_move()
    print(chosen_id)
    session['board'][chosen_id] = OPPONENT_SYMBOL

    if is_winner(OPPONENT_SYMBOL):
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
    time.sleep(1)
    if is_opponents_turn():
        opponents_move()
    else:
        emit('state_updated', {'board': session['board'], 'message': 'Your move', 'unlock': True})


def is_winner(symbol):
    win_conditions = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8],
        [0, 3, 6], [1, 4, 7], [2, 5, 8],
        [0, 4, 8], [2, 4, 6]
    ]

    for condition in win_conditions:
        if all(session['board'][i] == symbol for i in condition):
            return True

    return False


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

        if is_winner(PLAYER_SYMBOL):
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
    socketio.run(app, allow_unsafe_werkzeug=True)
