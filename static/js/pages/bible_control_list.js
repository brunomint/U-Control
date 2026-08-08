async function addBiblePassage() {
    const input = document.getElementById('newBibleRef');
    const reference = input.value.trim();

    if (!reference) {
        alert('Digite uma referência bíblica');
        return;
    }

    try {
        const response = await fetch('/api/bible/add_to_order', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reference: reference })
        });

        const data = await response.json();

        if (data.success) {
            // Recarrega a página para mostrar a nova passagem
            window.location.reload();
        } else {
            alert(data.error || 'Erro ao adicionar passagem');
        }
    } catch (error) {
        console.error('Erro:', error);
        alert('Erro ao adicionar passagem');
    }
}

// Enter para adicionar
document.getElementById('newBibleRef').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        addBiblePassage();
    }
});

async function removeBiblePassage(reference) {
    if (!confirm(`Remover "${reference}" da ordem do culto?`)) {
        return;
    }

    try {
        const response = await fetch('/api/bible/remove_from_order', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reference: reference })
        });

        const data = await response.json();

        if (data.success) {
            window.location.reload();
        } else {
            alert(data.error || 'Erro ao remover passagem');
        }
    } catch (error) {
        console.error('Erro:', error);
        alert('Erro ao remover passagem');
    }
}
