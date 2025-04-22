import uuid
import random
import re

def generate_room_id():
    """Generate a unique room ID"""
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
    """Generate a randomized bingo board from a list of phrases"""
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

def check_bingo(board):
    """Check if a board has a winning pattern"""
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