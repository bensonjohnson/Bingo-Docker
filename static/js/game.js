const socket = io();
const roomId = document.getElementById('roomId').textContent;
let username = document.getElementById('playerName').textContent;
let board = [];
let hasBingo = false;
let winners = [];
let originalBoard = null;
let currentlyViewingWinner = null;
let winningCells = [];

// Show join dialog if no username is provided
function showJoinDialog() {
    // Create modal container
    const modalOverlay = document.createElement('div');
    modalOverlay.className = 'modal-overlay';
    modalOverlay.style.zIndex = '2000';
    
    const modal = document.createElement('div');
    modal.className = 'join-modal';
    modal.style.backgroundColor = 'white';
    modal.style.padding = '20px';
    modal.style.borderRadius = '8px';
    modal.style.width = '90%';
    modal.style.maxWidth = '400px';
    modal.style.textAlign = 'center';
    
    const title = document.createElement('h2');
    title.textContent = 'Join Game';
    title.style.marginBottom = '20px';
    
    const inputLabel = document.createElement('label');
    inputLabel.textContent = 'Your Name:';
    inputLabel.style.display = 'block';
    inputLabel.style.marginBottom = '5px';
    inputLabel.style.fontWeight = 'bold';
    
    const usernameInput = document.createElement('input');
    usernameInput.type = 'text';
    usernameInput.placeholder = 'Enter your name';
    usernameInput.style.width = '100%';
    usernameInput.style.padding = '10px';
    usernameInput.style.marginBottom = '20px';
    usernameInput.style.borderRadius = '4px';
    usernameInput.style.border = '1px solid #ddd';
    
    const joinButton = document.createElement('button');
    joinButton.textContent = 'Join Game';
    joinButton.className = 'btn';
    
    // Handle join button click
    joinButton.addEventListener('click', () => {
        const name = usernameInput.value.trim();
        if (name) {
            username = name;
            localStorage.setItem('bingo_username', username);
            document.getElementById('playerName').textContent = username;
            
            // Remove the modal
            document.body.removeChild(modalOverlay);
            
            // Join the room
            socket.emit('join_room', {
                username: username,
                room_id: roomId
            });
        } else {
            alert('Please enter your name');
        }
    });
    
    // Add all elements to the modal
    modal.appendChild(title);
    modal.appendChild(inputLabel);
    modal.appendChild(usernameInput);
    modal.appendChild(joinButton);
    
    modalOverlay.appendChild(modal);
    document.body.appendChild(modalOverlay);
    
    usernameInput.focus();
}

// Render the bingo board
function renderBoard() {
    const boardElement = document.getElementById('bingoBoard');
    boardElement.innerHTML = '';
    
    // Add BINGO letters at the top
    const headerRow = document.createElement('div');
    headerRow.className = 'bingo-header-row';
    ['B', 'I', 'N', 'G', 'O'].forEach(letter => {
        const letterCell = document.createElement('div');
        letterCell.className = 'bingo-header-cell';
        letterCell.textContent = letter;
        headerRow.appendChild(letterCell);
    });
    boardElement.appendChild(headerRow);
    
    // Add the board cells
    for (let i = 0; i < board.length; i++) {
        const row = document.createElement('div');
        row.className = 'bingo-row';
        
        for (let j = 0; j < board[i].length; j++) {
            const cell = document.createElement('div');
            cell.className = 'bingo-cell';
            cell.dataset.row = i;
            cell.dataset.col = j;
            cell.textContent = board[i][j].text;
            
            if (board[i][j].marked) {
                cell.classList.add('marked');
                
                // Check if this is part of a winning line
                if (winningCells.some(wc => wc.row === i && wc.col === j)) {
                    cell.classList.add('winning-cell');
                }
            }
            
            cell.addEventListener('click', () => handleCellClick(i, j));
            row.appendChild(cell);
        }
        
        boardElement.appendChild(row);
    }
}

// Handle cell click
function handleCellClick(row, col) {
    if (!hasBingo) {
        socket.emit('mark_cell', {
            room_id: roomId,
            row: row,
            col: col
        });
    }
}

// Render player list
function renderPlayerList(players) {
    const playerListElement = document.getElementById('playerList');
    playerListElement.innerHTML = '';
    
    players.forEach(player => {
        const playerItem = document.createElement('li');
        playerItem.textContent = player;
        playerItem.id = 'player-' + player;
        playerListElement.appendChild(playerItem);
    });
}

// Show bingo notification
function showBingo() {
    hasBingo = true;
    const bingoStatusElement = document.getElementById('bingoStatus');
    bingoStatusElement.innerHTML = '<h2 class="bingo-win">BINGO!</h2>';
}

// Event handlers
document.addEventListener('DOMContentLoaded', () => {
    // Fallback to localStorage if username is not available from server
    if (!username || username === 'None') {
        username = localStorage.getItem('bingo_username');
        console.log('Using username from localStorage:', username);
    }
    
    // Join the room when page loads, or show join dialog if no username
    if (username && username !== 'None') {
        socket.emit('join_room', {
            username: username,
            room_id: roomId
        });
    } else {
        // Try to get username from localStorage
        const storedUsername = localStorage.getItem('bingo_username');
        if (storedUsername) {
            username = storedUsername;
            document.getElementById('playerName').textContent = username;
            socket.emit('join_room', {
                username: username,
                room_id: roomId
            });
        } else {
            showJoinDialog();
        }
    }
    
    // Copy room ID to clipboard
    document.getElementById('copyRoomId').addEventListener('click', () => {
        navigator.clipboard.writeText(roomId).then(() => {
            alert('Room ID copied to clipboard!');
        });
    });
    
    // Share game link
    document.getElementById('shareLink').addEventListener('click', () => {
        const joinURL = window.location.origin + '/join?room=' + roomId;
        navigator.clipboard.writeText(joinURL).then(() => {
            alert('Game link copied to clipboard! Share it with others to join this game.');
        });
    });
    
    // Handle "View Your Board" button click
    document.getElementById('viewYourBoard').addEventListener('click', () => {
        if (originalBoard) {
            // Restore the player's original board
            board = originalBoard;
            document.getElementById('boardTitle').textContent = 'Your Bingo Board';
            
            // Clear winning cells highlight if not the winner
            if (!hasBingo) {
                winningCells = [];
            }
            
            renderBoard();
            
            // Hide the button
            document.getElementById('viewYourBoard').style.display = 'none';
            
            // Reset the tracking
            currentlyViewingWinner = null;
        }
    });
});

// Socket event handlers
socket.on('room_joined', (data) => {
    board = data.board;
    hasBingo = data.has_bingo;
    renderBoard();
    renderPlayerList(data.players);
    
    if (hasBingo) {
        showBingo();
    }
});

socket.on('player_joined', (data) => {
    const playerList = document.getElementById('playerList');
    // Check if the player is already in the list to avoid duplicates
    const existingPlayer = document.getElementById('player-' + data.username);
    if (!existingPlayer) {
        const playerItem = document.createElement('li');
        playerItem.textContent = data.username;
        playerItem.id = 'player-' + data.username;
        playerList.appendChild(playerItem);
        console.log('Added player to list:', data.username);
    } else {
        console.log('Player already in list:', data.username);
    }
});

socket.on('cell_marked', (data) => {
    if (data.username === username) {
        const cell = document.querySelector(`.bingo-cell[data-row="${data.row}"][data-col="${data.col}"]`);
        if (cell) {
            if (data.marked) {
                cell.classList.add('marked');
            } else {
                cell.classList.remove('marked');
            }
        }
    }
});

socket.on('player_bingo', (data) => {
    if (!winners.includes(data.username)) {
        winners.push(data.username);
        
        // Add winner to the list
        const winnersListElement = document.getElementById('winnersList');
        const winnerItem = document.createElement('li');
        
        // Make the winner's name clickable to view their board
        winnerItem.innerHTML = `<a href="#" class="winner-link" data-username="${data.username}">${data.username}</a>`;
        winnersListElement.appendChild(winnerItem);
        
        // Add click event to view this winner's board
        winnerItem.querySelector('.winner-link').addEventListener('click', (e) => {
            e.preventDefault();
            
            // Save the original board if not already saved
            if (!originalBoard) {
                originalBoard = JSON.parse(JSON.stringify(board));
            }
            
            // Track which winner we're viewing
            currentlyViewingWinner = data.username;
            
            // Update the board with the winner's board
            board = data.board;
            winningCells = data.winning_cells;
            document.getElementById('boardTitle').textContent = `${data.username}'s Winning Board`;
            renderBoard();
            
            // Show the button to switch back to the user's board
            document.getElementById('viewYourBoard').style.display = 'block';
        });
        
        // If the current user won, show bingo message and store winning cells
        if (data.username === username) {
            showBingo();
            winningCells = data.winning_cells;
            renderBoard(); // Re-render to highlight winning cells
        }
    }
});

socket.on('error', (data) => {
    alert(data.message);
});