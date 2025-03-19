import os
import json
import uuid
import random
from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import SocketIO, join_room, leave_room, emit
import redis

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'bingo-secret-key-change-in-production')
socketio = SocketIO(app, cors_allowed_origins="*")

# Redis configuration
redis_host = os.environ.get('REDIS_HOST', 'localhost')
redis_port = int(os.environ.get('REDIS_PORT', 6379))
redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)

# Helper functions
def generate_room_id():
    return str(uuid.uuid4())[:8]

def generate_bingo_board(phrases, size=5):
    # Create a copy of phrases to avoid modifying the original
    phrases_copy = phrases.copy()
    # Shuffle phrases
    random.shuffle(phrases_copy)
    # Ensure we have enough phrases (25 for a 5x5 board)
    required_phrases = size * size
    if len(phrases_copy) < required_phrases:
        phrases_copy = phrases_copy * (required_phrases // len(phrases_copy) + 1)
    
    # Take only the required number of phrases
    selected_phrases = phrases_copy[:required_phrases]
    
    # Create the board as a 2D array
    board = []
    for i in range(size):
        row = []
        for j in range(size):
            index = i * size + j
            # For the center cell in a 5x5 board, use "FREE" (if it's a 5x5 board)
            if size == 5 and i == 2 and j == 2:
                row.append({"text": "FREE", "marked": True})
            else:
                row.append({"text": selected_phrases[index], "marked": False})
        board.append(row)
    
    return board

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/create')
def create():
    return render_template('create.html')

@app.route('/join')
def join():
    return render_template('join.html')

@app.route('/game/<room_id>')
def game(room_id):
    username = session.get('username')
    print(f"Game route accessed for room {room_id}, username from session: {username}")
    
    if not username:
        print(f"No username in session, redirecting to index")
        return redirect(url_for('index'))
    
    # Check if room exists
    room_data = redis_client.get(f'room:{room_id}')
    if not room_data:
        print(f"Room {room_id} not found in Redis, redirecting to index")
        return redirect(url_for('index'))
    
    print(f"Rendering game template for user {username} in room {room_id}")
    return render_template('game.html', room_id=room_id, username=username)

# Socket.IO events
@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('create_room')
def handle_create_room(data):
    username = data.get('username')
    phrases = data.get('phrases', [])
    
    if not username or not phrases:
        emit('error', {'message': 'Invalid data'})
        return
    
    # Generate a unique room ID
    room_id = generate_room_id()
    
    # Store user in session and save it
    session['username'] = username
    session.modified = True
    
    # Store room data in Redis
    room_data = {
        'creator': username,
        'phrases': phrases,
        'players': [username],
        'size': 5  # Default board size
    }
    redis_client.set(f'room:{room_id}', json.dumps(room_data))
    
    # Generate a bingo board for the creator
    board = generate_bingo_board(phrases)
    redis_client.set(f'player:{username}:{room_id}', json.dumps({
        'board': board,
        'has_bingo': False
    }))
    
    # Join the room
    join_room(room_id)
    
    # Respond with the room ID
    emit('room_created', {'room_id': room_id})

@socketio.on('join_room')
def handle_join_room(data):
    username = data.get('username')
    room_id = data.get('room_id')
    
    if not username or not room_id:
        emit('error', {'message': 'Invalid data'})
        return
    
    # Store user in session and save it
    session['username'] = username
    session.modified = True
    
    # Check if room exists
    room_data_str = redis_client.get(f'room:{room_id}')
    if not room_data_str:
        emit('error', {'message': 'Room not found'})
        return
    
    room_data = json.loads(room_data_str)
    
    # Add player to room if not already in
    if username not in room_data['players']:
        room_data['players'].append(username)
        redis_client.set(f'room:{room_id}', json.dumps(room_data))
    
    # Generate a board for the player if they don't have one yet
    player_data_str = redis_client.get(f'player:{username}:{room_id}')
    if not player_data_str:
        board = generate_bingo_board(room_data['phrases'])
        redis_client.set(f'player:{username}:{room_id}', json.dumps({
            'board': board,
            'has_bingo': False
        }))
    
    # Join the room
    join_room(room_id)
    
    # Notify others that a new player joined
    emit('player_joined', {'username': username}, room=room_id)
    
    # Get player's board
    player_data = json.loads(redis_client.get(f'player:{username}:{room_id}'))
    
    # Send room and player data
    emit('room_joined', {
        'room_id': room_id,
        'creator': room_data['creator'],
        'players': room_data['players'],
        'board': player_data['board'],
        'has_bingo': player_data['has_bingo']
    })

@socketio.on('mark_cell')
def handle_mark_cell(data):
    username = session.get('username')
    room_id = data.get('room_id')
    row = data.get('row')
    col = data.get('col')
    
    if not username or not room_id or row is None or col is None:
        emit('error', {'message': 'Invalid data'})
        return
    
    # Get player's board
    player_data_str = redis_client.get(f'player:{username}:{room_id}')
    if not player_data_str:
        emit('error', {'message': 'Player data not found'})
        return
    
    player_data = json.loads(player_data_str)
    board = player_data['board']
    
    # Toggle the marked state of the cell
    if 0 <= row < len(board) and 0 <= col < len(board[row]):
        board[row][col]['marked'] = not board[row][col]['marked']
        
        # Check if player has bingo
        has_bingo = check_bingo(board)
        player_data['has_bingo'] = has_bingo
        player_data['board'] = board
        
        # Update player data in Redis
        redis_client.set(f'player:{username}:{room_id}', json.dumps(player_data))
        
        # Notify the room about the cell update
        emit('cell_marked', {
            'username': username,
            'row': row,
            'col': col,
            'marked': board[row][col]['marked']
        }, room=room_id)
        
        # If player got bingo, notify the room
        if has_bingo:
            emit('player_bingo', {'username': username}, room=room_id)

@socketio.on('disconnect')
def handle_disconnect():
    username = session.get('username')
    print(f'Client disconnected: {username}')

def check_bingo(board):
    size = len(board)
    
    # Check rows
    for i in range(size):
        if all(board[i][j]['marked'] for j in range(size)):
            return True
    
    # Check columns
    for j in range(size):
        if all(board[i][j]['marked'] for i in range(size)):
            return True
    
    # Check diagonal (top-left to bottom-right)
    if all(board[i][i]['marked'] for i in range(size)):
        return True
    
    # Check diagonal (top-right to bottom-left)
    if all(board[i][size-1-i]['marked'] for i in range(size)):
        return True
    
    return False

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)