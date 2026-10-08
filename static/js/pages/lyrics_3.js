    function openMenu() {
      const menu = document.getElementById('menu');
      const toggleButton = document.getElementById('toggle-button');
  
      menu.classList.add('active');
    }
  
    // Fecha o menu se clicar fora
    document.addEventListener('click', function (event) {
      const menu = document.getElementById('menu');
      const toggleButton = document.getElementById('toggle-button');
  
      const isClickInsideMenu = menu.contains(event.target);
      const isClickOnButton = toggleButton.contains(event.target);
  
      if (!isClickInsideMenu && !isClickOnButton && menu.classList.contains('active')) {
        menu.classList.remove('active');
      }
    });
  
    // Impede que o clique dentro do menu feche ele
    document.getElementById('menu').addEventListener('click', function (event) {
      event.stopPropagation();
    });

    function closeMenu() {
      document.getElementById('menu').classList.remove('active');
    }
