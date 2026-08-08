const timerEl = document.getElementById('timer');
const labelEl = document.getElementById('label');
const socket = io.connect(window.location.protocol + '//' + window.location.host);
let intervalId = null;
let endTs = null;

function formatTime(ms) {
    const total = Math.max(0, ms);
    const m = Math.floor(total / 60000);
    const s = Math.floor((total % 60000) / 1000);
    return String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
}

function tick() {
    const remaining = endTs - Date.now();
    timerEl.textContent = formatTime(remaining);
    if (remaining <= 0) {
        clearInterval(intervalId);
        intervalId = null;
        timerEl.textContent = '00:00';
        timerEl.classList.add('finished');
    }
}

socket.on('countdown_start', function(data) {
    endTs = data.end_timestamp;
    labelEl.textContent = data.label || '';
    timerEl.classList.remove('finished');
    clearInterval(intervalId);
    intervalId = setInterval(tick, 500);
    tick();
});

socket.on('countdown_pause', function(data) {
    clearInterval(intervalId);
    intervalId = null;
    timerEl.textContent = formatTime(data.remaining_ms);
});

socket.on('countdown_resume', function(data) {
    endTs = data.end_timestamp;
    clearInterval(intervalId);
    intervalId = setInterval(tick, 500);
    tick();
});

socket.on('countdown_reset', function() {
    clearInterval(intervalId);
    intervalId = null;
    endTs = null;
    labelEl.textContent = '';
    timerEl.textContent = '--:--';
    timerEl.classList.remove('finished');
});

// Recupera estado ao carregar (ex: monitor recarregado durante um timer ativo)
fetch('/api/countdown/state')
    .then(function(r) { return r.json(); })
    .then(function(state) {
        if (state.active && !state.paused && state.end_timestamp) {
            endTs = state.end_timestamp;
            labelEl.textContent = state.label || '';
            timerEl.classList.remove('finished');
            intervalId = setInterval(tick, 500);
            tick();
        } else if (state.active && state.paused && state.paused_remaining != null) {
            labelEl.textContent = state.label || '';
            timerEl.textContent = formatTime(state.paused_remaining);
        }
    })
    .catch(function() {});
