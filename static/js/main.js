const translations = {
    en: {
        navHome: "Home",
        navExplore: "Explore",
        navSubmit: "Submit",
        navLogin: "Login",
        navRegister: "Sign Up",
        navLogout: "Logout",
        loginTitle: "Welcome Back",
        registerTitle: "Join XOTD",
        registerSubtitle: "Start sharing your knowledge today.",
        usernameLabel: "Username",
        passwordLabel: "Password",
        captchaLabel: "Verification",
        anonymousLabel: "Share Anonymously",
        noAccountMsg: "Don't have an account?",
        hasAccountMsg: "Already have an account?",
        title: "🍰 XOTD",
        subtitle: "Learn, discover, and share knowledge with the world, one day at a time.",
        todayHighlights: "Today's Highlights",
        contributor: "By",
        readMore: "Ref",
        noDataToday: "No one has shared anything today yet.",
        noData: "No data yet. Be the first to submit!",
        noResults: "No items match your search criteria.",
        wordTitle: "Word of the Day",
        conceptTitle: "Concept of the Day",
        exploreTitle: "Explore Past XOTDs",
        exploreSubtitle: "Browse all the amazing words and concepts shared by our community.",
        filterAll: "All",
        filterWords: "Words",
        filterConcepts: "Concepts",
        filterOthers: "Others",
        customTypesLabel: "Custom Categories",
        formTitle: "Share Your Knowledge",
        editTitle: "Edit Knowledge", // 新增编辑标题
        formType: "Type",
        optionWord: "Word",
        optionConcept: "Concept",
        optionOther: "Other (Custom)",
        formItemName: "Item Name",
        formDefinition: "Definition / Explanation",
        formExample: "Example Sentence (Optional)",
        formUrl: "Reference Links (Optional)",
        urlHelper: "e.g., wikipedia.org",
        submitBtn: "Submit",
        submitting: "Please wait...",
        placeholderItem: "e.g., K-omega SST / Ephemeral",
        placeholderDef: "Explain it in simple terms...",
        placeholderExample: "Provide an example of how it is used...",
        placeholderUrl: "wikipedia.org/wiki/...",
        placeholderCustomType: "e.g., Quote, Idiom...",
        placeholderSearch: "Search by keyword...",
        captchaPlaceholder: "Answer",
        successMsg: "🎉 Success! Redirecting...",
        errorMsg: "❌ Failed. Please try again.",
        confirmDelete: "Are you sure you want to permanently delete this item?" // 新增删除确认
    },
    zh: {
        navHome: "首页",
        navExplore: "发现",
        navSubmit: "上传",
        navLogin: "登录",
        navRegister: "注册",
        navLogout: "退出",
        loginTitle: "欢迎回来",
        registerTitle: "加入 XOTD",
        registerSubtitle: "今天就开始分享你的知识库吧。",
        usernameLabel: "用户名",
        passwordLabel: "密码 (至少 6 位)",
        captchaLabel: "验证码",
        anonymousLabel: "匿名分享",
        noAccountMsg: "还没有账号？",
        hasAccountMsg: "已经有账号了？",
        title: "🍰 XOTD",
        subtitle: "每天进步一点点，发现、学习并与世界分享知识。",
        todayHighlights: "今日精选",
        contributor: "贡献者",
        readMore: "参考",
        noDataToday: "今天还没有人分享内容哦。",
        noData: "暂无数据，快来贡献第一个吧！",
        noResults: "没有找到符合条件的分享内容。",
        wordTitle: "今日单词",
        conceptTitle: "今日概念",
        exploreTitle: "探索往期 XOTD",
        exploreSubtitle: "浏览社区分享的所有精彩词汇与概念。",
        filterAll: "全部",
        filterWords: "单词",
        filterConcepts: "概念",
        filterOthers: "其他",
        customTypesLabel: "自定义分类",
        formTitle: "分享你的知识",
        editTitle: "编辑内容", // 新增编辑标题
        formType: "分享类型",
        optionWord: "单词",
        optionConcept: "概念",
        optionOther: "其他 (自定义)",
        formItemName: "名称",
        formDefinition: "定义或解释",
        formExample: "例句或应用场景 (选填)",
        formUrl: "参考链接 (选填)",
        urlHelper: "例如：baike.baidu.com",
        submitBtn: "提交",
        submitting: "请稍候...",
        placeholderItem: "例如：内卷 / 正定矩阵",
        placeholderDef: "用通俗易懂的话解释它的含义...",
        placeholderExample: "提供一个使用的例子...",
        placeholderUrl: "zh.wikipedia.org/wiki/...",
        placeholderCustomType: "例如：名言、算法...",
        placeholderSearch: "输入关键词搜索...",
        captchaPlaceholder: "输入答案",
        successMsg: "🎉 成功！页面跳转中...",
        errorMsg: "❌ 失败，请重试。",
        confirmDelete: "您确定要永久删除这条内容吗？" // 新增删除确认
    }
};

let currentLang = localStorage.getItem('xotd_lang') || 'en';

function updateLanguage(lang) {
    currentLang = lang;
    localStorage.setItem('xotd_lang', lang);
    document.documentElement.lang = lang; 
    
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (translations[lang][key]) {
            el.textContent = translations[lang][key];
        }
    });

    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        const key = el.getAttribute('data-i18n-placeholder');
        if (translations[lang][key]) {
            el.placeholder = translations[lang][key];
        }
    });

    document.querySelectorAll('.bilingual-text').forEach(el => {
        if (el.getAttribute('data-lang') === lang) {
            el.classList.remove('hidden');
        } else {
            el.classList.add('hidden');
        }
    });
}

const langSwitch = document.getElementById('lang-switch');
if (langSwitch) {
    langSwitch.value = currentLang;
    langSwitch.addEventListener('change', (e) => {
        updateLanguage(e.target.value);
    });
}
updateLanguage(currentLang);


async function loadCaptcha() {
    const captchaText = document.getElementById('captcha-text');
    if (captchaText) {
        try {
            const res = await fetch('/api/captcha');
            const data = await res.json();
            captchaText.textContent = data.question;
        } catch (error) {
            console.error("Failed to load captcha");
        }
    }
}

const refreshCaptchaBtn = document.getElementById('refresh-captcha');
if (refreshCaptchaBtn) {
    refreshCaptchaBtn.addEventListener('click', loadCaptcha);
}
loadCaptcha();

async function handleAuthSubmit(e, url, btnId, statusId) {
    e.preventDefault();
    const btn = document.getElementById(btnId);
    const statusDiv = document.getElementById(statusId);
    
    const usernameInput = e.target.querySelector('input[type="text"]').value;
    const passwordInput = e.target.querySelector('input[type="password"]').value;
    const captchaEl = e.target.querySelector('#reg-captcha');
    const captchaVal = captchaEl ? captchaEl.value : null;

    const payload = { username: usernameInput, password: passwordInput };
    if (captchaVal !== null) {
        payload.captcha = captchaVal;
    }

    btn.disabled = true;
    btn.classList.add('opacity-75');

    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        statusDiv.className = 'mt-4 p-3 rounded-lg text-center text-sm font-medium block';
        if (response.ok) {
            statusDiv.classList.add('bg-green-50', 'text-green-700');
            statusDiv.textContent = translations[currentLang].successMsg;
            setTimeout(() => { window.location.href = '/'; }, 1000);
        } else {
            throw new Error(data.error || 'Authentication failed');
        }
    } catch (error) {
        statusDiv.className = 'mt-4 p-3 rounded-lg text-center text-sm font-medium block bg-red-50 text-red-700';
        statusDiv.textContent = '❌ ' + error.message;
        btn.disabled = false;
        btn.classList.remove('opacity-75');
        loadCaptcha();
        if(captchaEl) captchaEl.value = '';
    }
}

const loginForm = document.getElementById('login-form');
if (loginForm) loginForm.addEventListener('submit', (e) => handleAuthSubmit(e, '/api/login', 'login-btn', 'login-status'));

const regForm = document.getElementById('register-form');
if (regForm) regForm.addEventListener('submit', (e) => handleAuthSubmit(e, '/api/register', 'reg-btn', 'reg-status'));


// ==== 全局管理员删除监听逻辑 ====
document.addEventListener('click', async (e) => {
    const delBtn = e.target.closest('.delete-btn');
    if (delBtn) {
        if (!confirm(translations[currentLang].confirmDelete)) return;
        
        const itemId = delBtn.getAttribute('data-id');
        try {
            const response = await fetch(`/api/delete/${itemId}`, { method: 'DELETE' });
            if (response.ok) {
                // 删除成功后原地刷新页面以显示最新结果
                window.location.reload();
            } else {
                alert(translations[currentLang].errorMsg);
            }
        } catch (error) {
            console.error('Delete error:', error);
            alert('Network error.');
        }
    }
});


const typeSelect = document.getElementById('item-type');
const customTypeInput = document.getElementById('custom-type');
if (typeSelect && customTypeInput) {
    typeSelect.addEventListener('change', (e) => {
        if (e.target.value === 'other') {
            customTypeInput.classList.remove('hidden');
            customTypeInput.required = true;
        } else {
            customTypeInput.classList.add('hidden');
            customTypeInput.required = false;
            customTypeInput.value = '';
        }
    });
}

const addUrlBtn = document.getElementById('add-url-btn');
if (addUrlBtn) {
    addUrlBtn.addEventListener('click', () => {
        const container = document.getElementById('url-container');
        const newGroup = document.createElement('div');
        newGroup.className = 'flex items-center gap-2 mt-3';
        newGroup.innerHTML = `
            <input type="text" class="url-input w-full border-slate-300 rounded-lg shadow-sm focus:border-blue-500 focus:ring-blue-500 p-3 border bg-slate-50" placeholder="${translations[currentLang].placeholderUrl}">
            <button type="button" class="remove-url-btn p-3 bg-red-50 text-red-500 rounded-lg hover:bg-red-100 transition-colors" onclick="this.parentElement.remove()">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 12H4"></path></svg>
            </button>
        `;
        container.appendChild(newGroup);
    });
}

const submitForm = document.getElementById('submission-form');
if (submitForm) {
    submitForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const submitBtn = document.getElementById('submit-btn');
        const btnTextSpan = submitBtn.querySelector('span');
        const statusDiv = document.getElementById('status-message');

        submitBtn.disabled = true;
        submitBtn.classList.add('opacity-75', 'cursor-not-allowed');
        btnTextSpan.textContent = translations[currentLang].submitting;

        let reference_urls = [];
        document.querySelectorAll('.url-input').forEach(input => {
            let url = input.value.trim();
            if (url) {
                if (!url.startsWith('http://') && !url.startsWith('https://')) {
                    url = 'https://' + url;
                }
                reference_urls.push(url);
            }
        });

        let finalType = typeSelect.value;
        if (finalType === 'other') {
            finalType = customTypeInput.value.trim() || 'Other';
        }

        const isAnonymous = document.getElementById('is-anonymous') ? document.getElementById('is-anonymous').checked : false;
        
        // 核心：判断是新建还是编辑
        const editId = document.getElementById('edit-item-id') ? document.getElementById('edit-item-id').value : '';
        const endpoint = editId ? `/api/edit/${editId}` : '/api/submit';
        const method = editId ? 'PUT' : 'POST';

        const payload = {
            type: finalType,
            item: document.getElementById('item-name').value,
            definition: document.getElementById('item-definition').value,
            example: document.getElementById('item-example').value,
            reference_urls: reference_urls,
            is_anonymous: isAnonymous 
        };

        try {
            const response = await fetch(endpoint, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) throw new Error('Network response was not ok');
            
            statusDiv.className = 'mt-6 p-4 rounded-lg text-center text-sm font-medium block bg-green-50 text-green-700';
            statusDiv.textContent = translations[currentLang].successMsg;
            
            setTimeout(() => { window.location.href = '/'; }, 1000);
            
        } catch (error) {
            console.error('Submission Error:', error);
            statusDiv.className = 'mt-6 p-4 rounded-lg text-center text-sm font-medium block bg-red-50 text-red-700';
            statusDiv.textContent = translations[currentLang].errorMsg;
            submitBtn.disabled = false;
            submitBtn.classList.remove('opacity-75', 'cursor-not-allowed');
            btnTextSpan.textContent = translations[currentLang].submitBtn;
        } 
    });
}

// ==== Explore 页检索引擎 ====
const toggleOthersBtn = document.getElementById('toggle-others-btn');
const customTypesPanel = document.getElementById('custom-types-panel');
const searchInput = document.getElementById('search-input');
const datePicker = document.getElementById('date-picker');
const clearDateBtn = document.getElementById('clear-date-btn');
const filterBtns = document.querySelectorAll('.filter-btn');
const itemCards = document.querySelectorAll('.item-card');
const noResultsMsg = document.getElementById('no-results-msg');

let currentActiveFilter = 'all';

if (toggleOthersBtn && customTypesPanel) {
    toggleOthersBtn.addEventListener('click', () => {
        customTypesPanel.classList.toggle('hidden');
        customTypesPanel.classList.toggle('flex');
    });
}

function applyAllFilters() {
    if(!itemCards) return;
    
    const keyword = searchInput ? searchInput.value.trim().toLowerCase() : '';
    const selectedDate = datePicker ? datePicker.value : '';
    let visibleCount = 0;

    itemCards.forEach(card => {
        const cardType = card.getAttribute('data-type');
        const cardDate = card.getAttribute('data-date');
        const cardText = card.innerText.toLowerCase(); 

        let matchCategory = false;
        if (currentActiveFilter === 'all') {
            matchCategory = true;
        } else if (currentActiveFilter === 'only-others') {
            matchCategory = (cardType !== 'word' && cardType !== 'concept');
        } else {
            matchCategory = (cardType === currentActiveFilter);
        }

        let matchKeyword = (keyword === '') || cardText.includes(keyword);
        let matchDate = (selectedDate === '') || (cardDate === selectedDate);

        if (matchCategory && matchKeyword && matchDate) {
            card.style.display = 'flex';
            visibleCount++;
        } else {
            card.style.display = 'none';
        }
    });

    if (noResultsMsg) {
        if (visibleCount === 0 && itemCards.length > 0) {
            noResultsMsg.classList.remove('hidden');
        } else {
            noResultsMsg.classList.add('hidden');
        }
    }
}

if (searchInput) {
    searchInput.addEventListener('input', applyAllFilters);
}

if (datePicker) {
    datePicker.addEventListener('change', () => {
        if (datePicker.value !== '') {
            clearDateBtn.classList.remove('hidden');
        } else {
            clearDateBtn.classList.add('hidden');
        }
        applyAllFilters();
    });
}

if (clearDateBtn) {
    clearDateBtn.addEventListener('click', () => {
        datePicker.value = '';
        clearDateBtn.classList.add('hidden');
        applyAllFilters();
    });
}

if (filterBtns.length > 0) {
    filterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            filterBtns.forEach(b => {
                b.classList.remove('bg-slate-900', 'text-white', 'font-semibold');
                b.classList.add('bg-white', 'text-slate-600', 'font-medium');
            });
            btn.classList.remove('bg-white', 'text-slate-600', 'font-medium');
            btn.classList.add('bg-slate-900', 'text-white', 'font-semibold');

            currentActiveFilter = btn.getAttribute('data-filter');
            applyAllFilters();
        });
    });
}