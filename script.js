
const state = {
    coins: parseInt(localStorage.getItem('coins')) || 0,
    theme: 'offline',
    adCount: 0,
    board: Array(9).fill(null),
    isPlayerTurn: true
};

const ui = {
    showScreen: (id) => {
        document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
        document.getElementById(id).classList.add('active');
    },
    updateCoins: () => {
        document.getElementById('coin-count').innerText = state.coins;
        localStorage.setItem('coins', state.coins);
    }
};

const game = {
    start: () => {
        state.board = Array(9).fill(null);
        state.isPlayerTurn = true;
        document.querySelectorAll('.cell').forEach(c => c.innerText = '');
        document.getElementById('status-text').innerText = "Your Turn (X)";
    },
    handleMove: (idx) => {
        if (!state.board[idx] && state.isPlayerTurn) {
            state.board[idx] = 'X';
            document.querySelector(`[data-index='${idx}']`).innerText = 'X';
            if (game.checkWinner()) return;
            
            state.isPlayerTurn = false;
            document.getElementById('status-text').innerText = "AI is thinking...";
            setTimeout(game.aiMove, 600);
        }
    },
    aiMove: () => {
        const empty = state.board.map((v, i) => v === null ? i : null).filter(v => v !== null);
        if (empty.length > 0) {
            const move = empty[Math.floor(Math.random() * empty.length)];
            state.board[move] = 'O';
            document.querySelector(`[data-index='${move}']`).innerText = 'O';
            game.checkWinner();
            state.isPlayerTurn = true;
            document.getElementById('status-text').innerText = "Your Turn (X)";
        }
    },
    checkWinner: () => {
        const wins = [[0,1,2],[3,4,5],[6,7,8],[0,3,6],[1,4,7],[2,5,8],[0,4,8],[2,4,6]];
        for (let comb of wins) {
            const [a, b, c] = comb;
            if (state.board[a] && state.board[a] === state.board[b] && state.board[a] === state.board[c]) {
                game.end(state.board[a] === 'X' ? 'WIN' : 'LOSE');
                return true;
            }
        }
        if (!state.board.includes(null)) { game.end('DRAW'); return true; }
        return false;
    },
    end: (result) => {
        let reward = result === 'WIN' ? 50 : (result === 'DRAW' ? 20 : 5);
        state.coins += reward;
        ui.updateCoins();
        alert(`GAME OVER! Result: ${result}. Reward: ${reward} 💰`);
        ui.showScreen('menu-screen');
    },
    buyItem: (name, price) => {
        if (state.coins >= price) {
            state.coins -= price;
            ui.updateCoins();
            alert("SUCCESS! You have unlocked the " + name);
        } else {
            alert("Not enough coins!");
        }
    }
};

const ads = {
    showRewardAd: () => {
        alert("Playing Video Ad..."); // এখানে আসল Monetag show_YOUR_ZONE_ID() বসবে
        setTimeout(() => {
            state.coins += 20;
            ui.updateCoins();
            alert("Success! Received 20 Coins.");
        }, 2000);
    },
    watchThreeAds: () => {
        state.adCount++;
        if (state.adCount >= 3) {
            state.coins += 100;
            state.adCount = 0;
            ui.updateCoins();
            alert("Jackpot! You watched 3 ads and got 100 Coins.");
        } else {
            alert(`Ad finished! (${state.adCount}/3)`);
        }
    }
};

// Event Listeners
document.querySelectorAll('.cell').forEach(cell => {
    cell.addEventListener('click', () => game.handleMove(cell.dataset.index));
});

document.getElementById('theme-toggle').addEventListener('click', () => {
    document.body.classList.toggle('online-theme');
    document.body.classList.toggle('offline-theme');
    const isOnline = document.body.classList.contains('online-theme');
    document.getElementById('theme-toggle').innerText = isOnline ? "Switch to OFFLINE" : "Switch to ONLINE";
    document.getElementById('game-title').innerText = isOnline ? "NEON BATTLE" : "WOODEN BATTLE";
});

// Initial Setup
ui.updateCoins();
