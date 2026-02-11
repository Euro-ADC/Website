window.addEventListener('scroll', function() {
    const header = document.getElementById('main-header');
    const icon_menu = document.getElementById('div-icon-menu');
    if (window.scrollY > 50) {
        header.classList.add('scrolled');
        icon_menu.classList.add('scrolled');
    } else {
        header.classList.remove('scrolled');
        icon_menu.classList.remove('scrolled');
    }
});