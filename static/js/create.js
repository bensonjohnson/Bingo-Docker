const socket = io();
const NUM_PHRASE_INPUTS = 25; // We want 25 inputs (5x5 board with free space)

// Store all saved phrases
let savedPhrases = [];

// Initialize the phrase input boxes
function initPhraseInputs() {
    const phraseInputs = document.getElementById('phraseInputs');
    phraseInputs.innerHTML = '';
    
    // Get saved phrases right away
    socket.emit('get_saved_phrases');
    
    for (let i = 0; i < NUM_PHRASE_INPUTS; i++) {
        const inputContainer = document.createElement('div');
        inputContainer.className = 'phrase-input-container';
        
        // Create a select element with autocomplete
        const selectInput = document.createElement('select');
        selectInput.className = 'phrase-input';
        selectInput.id = 'phrase-' + i;
        
        // Add an empty default option
        const defaultOption = document.createElement('option');
        defaultOption.value = '';
        defaultOption.textContent = `Phrase ${i + 1}`;
        selectInput.appendChild(defaultOption);
        
        inputContainer.appendChild(selectInput);
        phraseInputs.appendChild(inputContainer);
        
        // Initialize Select2 on this input
        $(selectInput).select2({
            tags: true, // Allow new entries
            placeholder: `Phrase ${i + 1}`,
            width: '100%',
            allowClear: true,
            theme: "classic",
            dropdownParent: inputContainer,
            createTag: function (params) {
                return {
                    id: params.term,
                    text: params.term,
                    newTag: true
                };
            }
        });
        
        // Ensure proper sizing
        $(window).resize(function() {
            $('.select2-container').css('width', '100%');
        });
    }
}

// Update phrase suggestions when we receive saved phrases
socket.on('saved_phrases', (data) => {
    if (data.phrases && data.phrases.length > 0) {
        savedPhrases = data.phrases;
        
        // Update each select with the available phrases
        for (let i = 0; i < NUM_PHRASE_INPUTS; i++) {
            const select = $('#phrase-' + i);
            
            // Clear existing options except the default empty one
            select.find('option:not(:first)').remove();
            
            // Add all saved phrases as options
            savedPhrases.forEach(phrase => {
                const option = new Option(phrase, phrase, false, false);
                select.append(option);
            });
            
            // Refresh Select2
            select.trigger('change');
        }
    }
});

// Collect phrases from Select2 inputs
function collectPhrases() {
    const phrases = [];
    
    for (let i = 0; i < NUM_PHRASE_INPUTS; i++) {
        const value = $('#phrase-' + i).val();
        if (value) {
            phrases.push(value);
        }
    }
    
    return phrases;
}

// Fill phrase inputs with provided phrases
function fillPhraseInputs(phrases) {
    // Clear existing inputs
    for (let i = 0; i < NUM_PHRASE_INPUTS; i++) {
        $('#phrase-' + i).val('').trigger('change');
    }
    
    // Fill with provided phrases
    phrases.forEach((phrase, index) => {
        if (index < NUM_PHRASE_INPUTS) {
            // Create the option if it doesn't exist
            if (!$('#phrase-' + index).find(`option[value="${phrase}"]`).length) {
                const newOption = new Option(phrase, phrase, true, true);
                $('#phrase-' + index).append(newOption);
            }
            
            $('#phrase-' + index).val(phrase).trigger('change');
        }
    });
}

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

// Sample phrases for the bingo board
const samplePhrases = [
    "Someone mentions the weather",
    "Coffee break is mentioned",
    "Technical difficulties",
    "Someone says 'let's circle back'",
    "Someone joins late",
    "Someone's pet appears",
    "Awkward silence",
    "Someone apologizes for background noise",
    "Someone is on mute when trying to speak",
    "Someone says 'can you see my screen?'",
    "Internet connection issues",
    "Someone multitasking",
    "Someone has to leave early",
    "Someone shares the wrong screen",
    "Meeting goes over scheduled time",
    "Someone says 'we lost you for a second'",
    "Someone mentions being busy",
    "Email mentioned during call",
    "Someone's doorbell rings",
    "Someone uses corporate jargon",
    "Someone hasn't read the pre-meeting materials",
    "A child or family member interrupts",
    "Someone says 'quick question'",
    "Phone rings during meeting",
    "Someone asks 'can everyone hear me?'"
];

// Event handlers
document.addEventListener('DOMContentLoaded', () => {
    initPhraseInputs();
    
    // Create game button event handler
    document.getElementById('createGame').addEventListener('click', () => {
        const username = document.getElementById('username').value.trim();
        const phrases = collectPhrases();
        
        // Validate username
        const validation = validateUsername(username);
        if (!validation.isValid) {
            alert(validation.message);
            return;
        }
        
        // Check phrases count
        if (phrases.length < 24) {
            alert('Please enter at least 24 phrases');
            return;
        }
        
        // Save phrases to Redis for future use
        socket.emit('save_phrases', {
            phrases: phrases
        });
        
        // Create room
        socket.emit('create_room', {
            username: username,
            phrases: phrases
        });
    });
    
    // Load sample phrases button event handler
    document.getElementById('addSample').addEventListener('click', () => {
        fillPhraseInputs(samplePhrases);
    });
});

// Socket event handlers
socket.on('room_created', (data) => {
    console.log('Room created with ID:', data.room_id);
    // Store username in localStorage
    const username = document.getElementById('username').value.trim();
    localStorage.setItem('bingo_username', username);
    // Redirect with username as query parameter
    window.location.href = '/game/' + data.room_id + '?username=' + encodeURIComponent(username);
});

socket.on('error', (data) => {
    alert(data.message);
});