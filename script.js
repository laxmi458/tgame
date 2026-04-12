// --- CONFIGURATION ---
const REWARDS = { WIN: 50, LOSE: 10, DRAW: 20, AD: 20, DAILY: 100 };

const state = {
    coins: parseInt(localStorage.getItem('coins')) || 0,
    isOnline: false,
    board: Array(9).fill(null),
    currentPlayer: 'X',
    gameActive: true
};

const ui = {
    updateBalance: () => {
        document.getElementById('coin-count').innerText = state.coins;
        localStorage.setItem('coins', state.coins);
    },
    showScreen: (id) => {
        document.querySelectorAll('section').forEach(s => s.classList.remove('active'));
        document.getElementById(id).classList.add('active');
    }
};

const game = {
    init: () => {
        document.querySelectorAll('.cell').forEach(cell => {
            cell.addEventListener('click', (e) => game.handleMove(e));
        });
        ui.updateBalance();
        game.checkDailyBonus();
    },
    
    handleMove: (e) => {
        const idx = e.target.dataset.index;
        if(state.board[idx] || !state.gameActive) return;

        state.board[idx] = state.currentPlayer;
        e.target.innerText = state.currentPlayer;
        
        if(game.checkWin()) return game.end(state.currentPlayer === 'X' ? 'WIN' : 'LOSE');
        if(!state.board.includes(null)) return game.end('DRAW');

        state.currentPlayer = 'O';
        if(!state.isOnline) setTimeout(game.aiMove, 500);
    },

    aiMove: () => {
        const emptyCells = state.board.map((v, i) => v === null ? i : null).filter(v => v !== null);
        const randomIdx = emptyCells[Math.floor(Math.random() * emptyCells.length)];
        const cell = document.querySelector(`[data-index='${randomIdx}']`);
        state.board[randomIdx] = 'O';
        cell.innerText = 'O';
        if(game.checkWin()) return game.end('LOSE');
        state.currentPlayer = 'X';
    },

    checkWin: () => {
        const wins = [[0,1,2],[3,4,5],[6,7,8],[0,3,6],[1,4,7],[2,5,8],[0,4,8],[2,4,6]];
        return wins.some(comb => {
            return state.board[comb[0]] && state.board[comb[0]] === state.board[comb[1]] && state.board[comb[0]] === state.board[comb[2]];
        });
    },

    end: (result) => {
        state.gameActive = false;
        state.coins += REWARDS[result];
        alert(`Game Over: ${result}! You earned ${REWARDS[result]} coins.`);
        ui.updateBalance();
        ui.showScreen('menu-screen');
        game.reset();
    },

    reset: () => {
        state.board = Array(9).fill(null);
        state.currentPlayer = 'X';
        state.gameActive = true;
        document.querySelectorAll('.cell').forEach(c => c.innerText = '');
    },

    checkDailyBonus: () => {
        const lastLogin = localStorage.getItem('lastLogin');
        const today = new Date().toDateString();
        if(lastLogin !== today) {
            state.coins += REWARDS.DAILY;
            localStorage.setItem('lastLogin', today);
            ui.updateBalance();
            alert("Daily Bonus: +100 Coins!");
        }
    }
};

// Toggle Theme Logic
document.getElementById('theme-toggle').addEventListener('click', () => {
    state.isOnline = !state.isOnline;
    document.body.className = state.isOnline ? 'online-theme' : 'offline-theme';
    document.getElementById('theme-toggle').innerText = state.isOnline ? 'Switch to OFFLINE' : 'Switch to ONLINE';
    document.getElementById('game-title').innerText = state.isOnline ? 'NEON BATTLE' : 'WOODEN TIC-TAC-TOE';
});

game.init();
