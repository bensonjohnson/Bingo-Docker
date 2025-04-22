const socket = io();

// Validate username
function validateUsername(username) {
    if (!username) {
        return { isValid: false, message: 'Please enter your name' };
    }
    
    // Check length
    if (username.length < 3 || username.length > 20) {
        return { isValid: false, message: 'Your name must be between 3 and 20 characters' };
    }
    
    // Check for invalid characters using regex
    const validUsernamePattern = /^[A-Za-z0-9 _.,-]+$/;
    if (!validUsernamePattern.test(username)) {
        return { isValid: false, message: 'Your name can only contain letters, numbers, spaces, and basic punctuation.' };
    }
    
    // Check for potentially dangerous patterns
    const dangerousPatterns = [';', '&', '|', '>', '<', '$', '`', '\\', 'eval', 'exec'];
    const hasDangerousPattern = dangerousPatterns.some(pattern => username.includes(pattern));
    if (hasDangerousPattern) {
        return { isValid: false, message: 'Your name contains invalid characters' };
    }
    
    return { isValid: true };
}

// Event handlers
document.addEventListener('DOMContentLoaded', () => {
    // Get URL parameters
    const urlParams = new URLSearchParams(window.location.search);
    const roomParam = urlParams.get('room');
    
    // If room ID is in the URL, pre-fill the field
    if (roomParam) {
        document.getElementById('roomId').value = roomParam;
        
        // Focus on the username field instead
        document.getElementById('username').focus();
        
        // If we have a username in localStorage, pre-fill it
        const storedUsername = localStorage.getItem('bingo_username');
        if (storedUsername) {
            document.getElementById('username').value = storedUsername;
            // Focus on the join button
            document.getElementById('joinGame').focus();
        }
    }
    
    // Form submission
    document.getElementById('joinForm').addEventListener('submit', (e) => {
        e.preventDefault(); // Prevent form submission
        
        const username = document.getElementById('username').value.trim();
        const roomId = document.getElementById('roomId').value.trim();
        
        // Validate username
        const validation = validateUsername(username);
        if (!validation.isValid) {
            alert(validation.message);
            return;
        }
        
        if (!roomId) {
            alert('Please enter a room ID');
            return;
        }
        
        socket.emit('join_room', {
            username: username,
            room_id: roomId
        });
    });
});

// Socket event handlers
socket.on('room_joined', (data) => {
    // Store username in localStorage
    const username = document.getElementById('username').value.trim();
    localStorage.setItem('bingo_username', username);
    // Redirect with username as query parameter
    window.location.href = '/game/' + data.room_id + '?username=' + encodeURIComponent(username);
});

socket.on('error', (data) => {
    alert(data.message);
});