function updateClock() {
    const now = new Date();
    const options = { weekday: 'long', month: 'long', day: 'numeric' };
    document.getElementById('date').textContent = now.toLocaleDateString(ucLocale(), options);
    document.getElementById('time').textContent = now.toLocaleTimeString(ucLocale(), { hour: '2-digit', minute: '2-digit' });
}
setInterval(updateClock, 1000);
updateClock();
