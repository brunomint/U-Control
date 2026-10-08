function copyUrl(url) {
    navigator.clipboard.writeText(url)
        .then(() => window.ucToast('Link copiado'))
        .catch(() => window.ucToast('Não deu pra copiar. Selecione o endereço e copie manualmente.', 'error'));
}
