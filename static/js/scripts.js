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

function toggleMenu() {
    const menu = document.getElementById('side-menu');
    const overlay = document.getElementById('overlay');
    const wrapper = document.getElementById('main-wrapper');

    menu.classList.toggle('active');
    overlay.classList.toggle('active');
    wrapper.classList.toggle('blurred');
}