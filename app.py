import os
from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import SocketIO, join_room, leave_room, emit
from database import Database
from utils import validate_username, generate_room_id, check_bingo

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'bingo-secret-key-change-in-production')
socketio = SocketIO(app, cors_allowed_origins="*", manage_session=False)

# Initialize database
db = Database()

# Flask routes
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
    
    # Store username in session for future requests
    session['username'] = username
    session.modified = True
    
    # Check if room exists
    room_data = db.get_room(room_id)
    if not room_data:
        print(f"Room {room_id} not found in Redis, redirecting to index")
        return redirect(url_for('index'))
    
    print(f"Rendering game template for user {username} in room {room_id}")
    return render_template('game.html', room_id=room_id, username=username)

# Socket.IO event handlers
@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('save_phrases')
def handle_save_phrases(data):
    phrases = data.get('phrases', [])
    
    if not phrases:
        emit('error', {'message': 'No phrases to save'})
        return
    
    count = db.save_phrases(phrases)
    emit('phrases_saved', {'count': count})

@socketio.on('get_saved_phrases')
def handle_get_saved_phrases():
    saved_phrases = db.get_saved_phrases()
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
    
    # Store user in session
    session['username'] = username
    session.modified = True
    
    # Create room in database
    db.create_room(room_id, username, phrases)
    
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
    
    # Store user in session
    session['username'] = username
    session.modified = True
    
    # Get room data
    room_data = db.get_room(room_id)
    if not room_data:
        emit('error', {'message': 'Room not found'})
        return
    
    # Add player to room if not already in
    room_data = db.add_player_to_room(room_id, username)
    
    # Get or create player data
    player_data = db.get_player(username, room_id)
    if not player_data:
        player_data = db.create_player(username, room_id)
    
    # Join the room
    join_room(room_id)
    
    # Notify others that a new player joined
    emit('player_joined', {'username': username}, room=room_id, skip_sid=request.sid)
    
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
    
    # Get player's data
    player_data = db.get_player(username, room_id)
    if not player_data:
        emit('error', {'message': 'Player data not found'})
        return
    
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
        
        # Update player data in database
        db.update_player(username, room_id, player_data)
        
        # Notify the room about the cell update
        emit('cell_marked', {
            'username': username,
            'row': row,
            'col': col,
            'marked': board[row][col]['marked']
        }, room=room_id)
        
        # If player got bingo, notify the room
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

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)