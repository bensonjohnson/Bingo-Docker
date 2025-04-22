import os
import json
import redis
from utils import generate_bingo_board

class Database:
    def __init__(self):
        """Initialize the Redis database connection"""
        self.redis_host = os.environ.get('REDIS_HOST', 'localhost')
        self.redis_port = int(os.environ.get('REDIS_PORT', 6379))
        self.client = redis.Redis(
            host=self.redis_host, 
            port=self.redis_port, 
            db=0, 
            decode_responses=True
        )

    def create_room(self, room_id, creator, phrases, size=5):
        """Create a new room in Redis"""
        room_data = {
            'creator': creator,
            'phrases': phrases,
            'players': [creator],
            'size': size
        }
        self.client.set(f'room:{room_id}', json.dumps(room_data))
        
        # Generate a bingo board for the creator
        board = generate_bingo_board(phrases, size)
        self.create_player(creator, room_id, board)
        
        return room_data
        
    def get_room(self, room_id):
        """Get room data from Redis"""
        room_data_str = self.client.get(f'room:{room_id}')
        if not room_data_str:
            return None
        return json.loads(room_data_str)
        
    def add_player_to_room(self, room_id, username):
        """Add a player to a room"""
        room_data = self.get_room(room_id)
        if not room_data:
            return None
        
        if username not in room_data['players']:
            room_data['players'].append(username)
            self.client.set(f'room:{room_id}', json.dumps(room_data))
        
        return room_data
    
    def create_player(self, username, room_id, board=None):
        """Create a player in a room with an optional board"""
        if not board:
            room_data = self.get_room(room_id)
            if not room_data:
                return None
            board = generate_bingo_board(room_data['phrases'])
            
        player_data = {
            'board': board,
            'has_bingo': False
        }
        self.client.set(f'player:{username}:{room_id}', json.dumps(player_data))
        
        return player_data
    
    def get_player(self, username, room_id):
        """Get player data from Redis"""
        player_data_str = self.client.get(f'player:{username}:{room_id}')
        if not player_data_str:
            return None
        return json.loads(player_data_str)
    
    def update_player(self, username, room_id, player_data):
        """Update player data in Redis"""
        self.client.set(f'player:{username}:{room_id}', json.dumps(player_data))
    
    def save_phrases(self, phrases):
        """Save phrases to Redis for future use"""
        saved_phrases_str = self.client.get('saved_phrases')
        saved_phrases = []
        
        if saved_phrases_str:
            saved_phrases = json.loads(saved_phrases_str)
        
        # Add new phrases, avoiding duplicates
        for phrase in phrases:
            if phrase not in saved_phrases:
                saved_phrases.append(phrase)
        
        # Save back to Redis
        self.client.set('saved_phrases', json.dumps(saved_phrases))
        
        return len(saved_phrases)
    
    def get_saved_phrases(self):
        """Get saved phrases from Redis"""
        saved_phrases_str = self.client.get('saved_phrases')
        if not saved_phrases_str:
            return []
        return json.loads(saved_phrases_str)