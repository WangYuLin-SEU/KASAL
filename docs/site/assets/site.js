'use strict';
(() => {
  const root = document.documentElement;
  let language = 'en';
  let view = 'main';
  const image = document.getElementById('interface-image');
  const imageLink = document.getElementById('interface-link');
  const caption = document.getElementById('interface-caption');
  const captions = {
    main: {en:'Browse objects, adjust symmetry settings, and analyze individual objects or run an incremental batch.',zh:'浏览物体、调整对称设置，分析单个物体或运行增量批处理。'},
    setup: {en:'Choose the dataset folder, interface language, preprocessing options and compute device.',zh:'选择数据集目录、界面语言、预处理选项和计算设备。'}
  };
  function updateScreenshot() {
    const path = `assets/v2-${view === 'main' ? '2' : '1'}-${language === 'en' ? 'en' : 'ch'}.png`;
    image.src = path; imageLink.href = path;
    image.alt = language === 'en' ? (view === 'main' ? 'KASAL analysis interface' : 'KASAL setup interface') : (view === 'main' ? 'KASAL 分析界面' : 'KASAL 设置界面');
    caption.textContent = captions[view][language];
    document.querySelectorAll('[data-view]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.view === view)));
  }
  function setLanguage(next) {
    language = next === 'zh' ? 'zh' : 'en';
    root.dataset.lang = language; root.lang = language === 'zh' ? 'zh-CN' : 'en';
    document.title = language === 'zh' ? 'KASAL | 三维旋转对称研究系列' : 'KASAL | 3D Rotational Symmetry Research';
    document.querySelectorAll('[data-language]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.language === language)));
    document.querySelectorAll('[data-href-en]').forEach(a => { a.href = a.dataset[language === 'en' ? 'hrefEn' : 'hrefZh']; });
    document.querySelectorAll('[data-text-en]').forEach(el => { el.textContent = el.dataset[language === 'en' ? 'textEn' : 'textZh']; });
    document.querySelectorAll('[data-aria-en]').forEach(el => { el.setAttribute('aria-label', el.dataset[language === 'en' ? 'ariaEn' : 'ariaZh']); });
    document.querySelectorAll('[data-alt-en]').forEach(el => { el.alt = el.dataset[language === 'en' ? 'altEn' : 'altZh']; });
    document.querySelector('.topnav').setAttribute('aria-label', language === 'en' ? 'Main navigation' : '主导航');
    document.querySelector('.section-nav').setAttribute('aria-label', language === 'en' ? 'Page sections' : '页面章节');
    document.querySelector('.language-switch').setAttribute('aria-label', language === 'en' ? 'Language' : '语言');
    document.querySelector('[aria-label="Interface screenshot"], [aria-label="界面截图"]').setAttribute('aria-label',language === 'en' ? 'Interface screenshot' : '界面截图');
    document.querySelector('.install-tabs').setAttribute('aria-label',language === 'en' ? 'Installation method' : '安装方式');
    try { localStorage.setItem('kasal-site-language',language); } catch (_) { /* Storage can be disabled. */ }
    updateScreenshot();
  }
  const tabs = [...document.querySelectorAll('[data-tab]')];
  function activateTab(name, focus = false) {
    tabs.forEach(tab => {
      const active = tab.dataset.tab === name;
      tab.setAttribute('aria-selected',String(active)); tab.tabIndex = active ? 0 : -1;
      document.getElementById(tab.getAttribute('aria-controls')).hidden = !active;
      if (active && focus) tab.focus();
    });
  }
  tabs.forEach((tab,i) => {
    tab.addEventListener('click',() => activateTab(tab.dataset.tab));
    tab.addEventListener('keydown',event => {
      let index;
      if (event.key === 'ArrowRight') index = (i + 1) % tabs.length;
      if (event.key === 'ArrowLeft') index = (i + tabs.length - 1) % tabs.length;
      if (event.key === 'Home') index = 0;
      if (event.key === 'End') index = tabs.length - 1;
      if (index !== undefined) { event.preventDefault(); activateTab(tabs[index].dataset.tab,true); }
    });
  });
  document.querySelectorAll('[data-language]').forEach(button => button.addEventListener('click',() => setLanguage(button.dataset.language)));
  document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click',() => { view = button.dataset.view; updateScreenshot(); }));
  const status = document.getElementById('copy-status');
  document.querySelectorAll('[data-copy]').forEach(button => {
    let timer;
    const original = button.innerHTML;
    button.addEventListener('click',async () => {
      const pre = document.getElementById(button.dataset.copy);
      clearTimeout(timer);
      try {
        if (!navigator.clipboard || !window.isSecureContext) throw new Error('Clipboard unavailable');
        await navigator.clipboard.writeText(pre.textContent);
        button.textContent = language === 'en' ? 'Copied!' : '已复制';
        status.textContent = language === 'en' ? 'Copied to clipboard.' : '已复制到剪贴板。';
      } catch (_) {
        const range = document.createRange(); range.selectNodeContents(pre);
        const selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range);
        button.textContent = language === 'en' ? 'Selected' : '已选中';
        status.textContent = language === 'en' ? 'Text selected. Press Control+C or Command+C to copy.' : '文字已选中，请按 Ctrl+C 或 Command+C 复制。';
      }
      timer = setTimeout(() => { button.innerHTML = original; },1800);
    });
  });
  let saved;
  try { saved = localStorage.getItem('kasal-site-language'); } catch (_) {}
  setLanguage(saved === 'zh' ? 'zh' : 'en');
  activateTab('pypi');
})();
