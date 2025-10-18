// 页面动画和交互效果
document.addEventListener('DOMContentLoaded', function() {
    // 添加页面加载动画
    document.body.style.opacity = '0';
    setTimeout(() => {
        document.body.style.transition = 'opacity 0.5s ease';
        document.body.style.opacity = '1';
    }, 100);
    
    // 为页面元素添加进入动画
    const cards = document.querySelectorAll('.card');
    cards.forEach((card, index) => {
        card.style.animationDelay = `${index * 0.1}s`;
        card.classList.add('fade-in-up');
    });

    // 为按钮添加悬停效果
    const buttons = document.querySelectorAll('.btn');
    buttons.forEach(btn => {
        btn.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-3px) scale(1.05)';
        });
        
        btn.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0) scale(1)';
        });
    });
    
    // 为表单添加实时验证效果
    const inputs = document.querySelectorAll('.form-control');
    inputs.forEach(input => {
        input.addEventListener('focus', function() {
            this.parentElement.classList.add('glow');
        });
        
        input.addEventListener('blur', function() {
            this.parentElement.classList.remove('glow');
        });
    });
    
    // 为卡片添加悬停效果
    const hoverCards = document.querySelectorAll('.card');
    hoverCards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.classList.add('glow');
        });
        
        card.addEventListener('mouseleave', function() {
            this.classList.remove('glow');
        });
    });
    
    // 添加滚动动画
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('fade-in-up');
            }
        });
    }, observerOptions);
    
    // 观察所有需要动画的元素
    document.querySelectorAll('.card, .table, .alert').forEach(el => {
        observer.observe(el);
    });
});