        function ajustarFonteParaCabimento(selector) {
            const elementos = document.querySelectorAll(selector);
        
            elementos.forEach(el => {
                let fontSize = parseFloat(window.getComputedStyle(el).fontSize);
                const minFontSize = 1; // tamanho mínimo de fonte em px
        
                // Enquanto o conteúdo for maior que o contêiner e ainda houver margem para reduzir
                while (el.scrollWidth > el.clientWidth && fontSize > minFontSize) {
                    fontSize -= 1;
                    el.style.fontSize = fontSize + 'px';
                }
            });
        }
        
        // Ajusta ao carregar
        window.addEventListener('load', () => {
            ajustarFonteParaCabimento('.section-link');
            ajustarFonteParaCabimento('.section-title');
            ajustarFonteParaCabimento('.main-content');
        });
        
        // Ajusta ao redimensionar a tela
        window.addEventListener('resize', () => {
            ajustarFonteParaCabimento('.section-link');
            ajustarFonteParaCabimento('.section-title');
            ajustarFonteParaCabimento('.main-content');
        });
