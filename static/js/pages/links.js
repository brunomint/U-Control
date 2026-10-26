function copyUrl(url) {
    navigator.clipboard.writeText(url)
        .then(() => window.ucToast(_t('Link copiado')))
        .catch(() => window.ucToast(_t('Não deu pra copiar. Selecione o endereço e copie manualmente.'), 'error'));
}
