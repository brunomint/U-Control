// Tradução no JS — mesmo dicionário do servidor (i18n.py). Em português
// não há dicionário: _t devolve o próprio texto. Valores entre chaves:
// _t('{n} músicas', { n: 3 }).
(function () {
    const dic = window.UC_I18N || {};
    window._t = function (texto, valores) {
        let s = Object.prototype.hasOwnProperty.call(dic, texto) && dic[texto] ? dic[texto] : texto;
        if (valores) s = s.replace(/\{(\w+)\}/g, (m, k) => (k in valores ? valores[k] : m));
        return s;
    };
    // Idioma das datas (toLocaleDateString): o lang do <html> (i18n.py)
    window.ucLocale = function () { return document.documentElement.lang || 'pt-BR'; };
})();
