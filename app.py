import os
import json
import uuid
import random
import re
from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import SocketIO, join_room, leave_room, emit
import redis

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'bingo-secret-key-change-in-production')
socketio = SocketIO(app, cors_allowed_origins="*", manage_session=False)

# Redis configuration
redis_host = os.environ.get('REDIS_HOST', 'localhost')
redis_port = int(os.environ.get('REDIS_PORT', 6379))
redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)

# Helper functions
def generate_room_id():
    return str(uuid.uuid4())[:8]

def validate_username(username):
    """
    Validates username to prevent command injection and ensure it meets requirements.
    Returns (is_valid, error_message) tuple.
    """
    # Check if username is empty or None
    if not username or not isinstance(username, str):
        return False, "Username cannot be empty"
    
    # Check length (3-20 characters)
    if len(username) < 3 or len(username) > 20:
        return False, "Username must be between 3 and 20 characters"
    
    # Only allow alphanumeric characters and some safe symbols
    # This regex pattern allows letters, numbers, spaces, and common safe symbols
    if not re.match(r'^[A-Za-z0-9 _.,-]+$', username):
        return False, "Username contains invalid characters. Use only letters, numbers, spaces, and basic punctuation"
    
    # Check for potentially dangerous sequences
    dangerous_patterns = [
        ';', '&', '|', '>', '<', '$', '`', '\\', 
        'eval', 'exec', 'System', 'bash', 'cmd', 
        'powershell', 'script', 'function'
    ]
    
    for pattern in dangerous_patterns:
        if pattern in username:
            return False, "Username contains invalid characters"
    
    return True, ""

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
    # Get username from query parameter or fallback to session
    username = request.args.get('username') or session.get('username')
    print(f"Game route accessed for room {room_id}, username: {username}")
    
    if not username:
        print(f"No username found, redirecting to index")
        return redirect(url_for('index'))
    
    # Validate username
    is_valid, error_message = validate_username(username)
    if not is_valid:
        print(f"Invalid username: {error_message}")
        return redirect(url_for('index'))
    
    # Store username in session anyway for future requests
    session['username'] = username
    session.modified = True
    
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

@socketio.on('save_phrases')
def handle_save_phrases(data):
    phrases = data.get('phrases', [])
    
    if not phrases:
        emit('error', {'message': 'No phrases to save'})
        return
    
    # Get existing phrases from Redis
    saved_phrases_str = redis_client.get('saved_phrases')
    saved_phrases = []
    
    if saved_phrases_str:
        saved_phrases = json.loads(saved_phrases_str)
    
    # Add new phrases, avoiding duplicates
    for phrase in phrases:
        if phrase not in saved_phrases:
            saved_phrases.append(phrase)
    
    # Save back to Redis
    redis_client.set('saved_phrases', json.dumps(saved_phrases))
    
    emit('phrases_saved', {'count': len(saved_phrases)})

@socketio.on('get_saved_phrases')
def handle_get_saved_phrases():
    # Get saved phrases from Redis
    saved_phrases_str = redis_client.get('saved_phrases')
    saved_phrases = []
    
    if saved_phrases_str:
        saved_phrases = json.loads(saved_phrases_str)
    
    emit('saved_phrases', {'phrases': saved_phrases})

@socketio.on('create_room')
def handle_create_room(data):
    username = data.get('username')
    phrases = data.get('phrases', [])
    
    if not username or not phrases:
        emit('error', {'message': 'Invalid data'})
        return
    
    # Validate username
    is_valid, error_message = validate_username(username)
    if not is_valid:
        emit('error', {'message': error_message})
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
    
    # Validate username
    is_valid, error_message = validate_username(username)
    if not is_valid:
        emit('error', {'message': error_message})
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
    
    # Notify others (but not the current player) that a new player joined
    emit('player_joined', {'username': username}, room=room_id, skip_sid=request.sid)
    
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
        bingo_result = check_bingo(board)
        player_data['has_bingo'] = bingo_result['has_bingo']
        if bingo_result['has_bingo']:
            player_data['winning_cells'] = bingo_result['winning_cells']
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
        
        # If player got bingo, notify the room with their board and winning info
        if bingo_result['has_bingo']:
            emit('player_bingo', {
                'username': username,
                'board': board,
                'winning_cells': bingo_result['winning_cells'],
                'winning_type': bingo_result['type'],
                'winning_index': bingo_result['index']
            }, room=room_id)

@socketio.on('disconnect')
def handle_disconnect():
    username = session.get('username')
    print(f'Client disconnected: {username}')

def check_bingo(board):
    size = len(board)
    winning_cells = []
    
    # Check rows
    for i in range(size):
        if all(board[i][j]['marked'] for j in range(size)):
            winning_cells = [{'row': i, 'col': j} for j in range(size)]
            return {'has_bingo': True, 'winning_cells': winning_cells, 'type': 'row', 'index': i}
    
    # Check columns
    for j in range(size):
        if all(board[i][j]['marked'] for i in range(size)):
            winning_cells = [{'row': i, 'col': j} for i in range(size)]
            return {'has_bingo': True, 'winning_cells': winning_cells, 'type': 'column', 'index': j}
    
    # Check diagonal (top-left to bottom-right)
    if all(board[i][i]['marked'] for i in range(size)):
        winning_cells = [{'row': i, 'col': i} for i in range(size)]
        return {'has_bingo': True, 'winning_cells': winning_cells, 'type': 'diagonal', 'index': 1}
    
    # Check diagonal (top-right to bottom-left)
    if all(board[i][size-1-i]['marked'] for i in range(size)):
        winning_cells = [{'row': i, 'col': size-1-i} for i in range(size)]
        return {'has_bingo': True, 'winning_cells': winning_cells, 'type': 'diagonal', 'index': 2}
    
    return {'has_bingo': False, 'winning_cells': []}

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)