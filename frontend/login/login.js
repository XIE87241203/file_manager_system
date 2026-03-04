/**
 * 用途：登录页逻辑管理，处理用户登录、表单验证及环境初始化
 */
const Login = {
    /**
     * @description 用途说明：初始化登录页面，初始化多语言，清除旧 Token 并加载版本号
     * @returns {void} - 返回值说明：无
     */
    init() {
        // 初始化多语言 (登录前默认使用本地缓存或英文)
        I18nManager.init();
        I18nManager.render();

        // 清空认证信息
        Request.eraseCookie('token');
        sessionStorage.removeItem('username');

        // 绑定回车键事件
        this.bindEvents();

        // 获取并显示版本号
        this.fetchAndDisplayAppVersion();
    },

    /**
     * @description 用途说明：为表单输入框绑定回车事件以及为登录按钮绑定点击事件
     * @returns {void} - 返回值说明：无
     */
    bindEvents() {
        ['username', 'password'].forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.addEventListener('keypress', (event) => {
                    if (event.key === 'Enter') {
                        this.handleLogin();
                    }
                });
            }
        });

        // 绑定登录按钮点击事件
        const loginBtn = document.getElementById('loginBtn');
        if (loginBtn) {
            loginBtn.onclick = () => this.handleLogin();
        }
    },

    /**
     * @description 用途说明：从后端获取应用版本号并渲染到页面页脚
     * @returns {void} - 返回值说明：无
     */
    fetchAndDisplayAppVersion() {
        LoginRequest.getVersion(
            (data) => {
                if (data && data.version) {
                    const versionDisplay = document.getElementById('app-version-display');
                    if (versionDisplay) {
                        versionDisplay.textContent = `${I18nManager.t('home.version')}: ${data.version}`;
                    }
                }
            },
            (msg) => {
                console.error('获取版本号失败:', msg);
            }
        );
    },

    /**
     * @description 用途说明：执行登录逻辑，包括表单校验、密码加密、发起请求及成功后的状态持久化与跳转
     * @returns {void} - 返回值说明：无
     */
    handleLogin() {
        const username = document.getElementById('username').value.trim();
        const password = document.getElementById('password').value;

        // 表单校验
        if (!username || !password) {
            Toast.show(I18nManager.t('login.username_placeholder'));
            return;
        }

        // 自动使用当前页面 origin 作为 API 基础地址
        const apiUrl = window.location.origin;
        sessionStorage.setItem('baseUrl', apiUrl);

        // 前端 SHA-256 加密
        const passwordHash = CryptoJS.SHA256(password).toString();

        const loginData = {
            username: username,
            password_hash: passwordHash
        };

        // 调用封装的 API 请求
        LoginRequest.login(
            loginData,
            (data) => {
                if (data && data.token) {
                    // 保存 Token (有效期 6 小时)
                    Request.setCookie('token', data.token, 6);
                    // 缓存用户名
                    sessionStorage.setItem('username', username);
                    // 跳转至首页
                    window.location.href = '../home/home.html';
                } else {
                    Toast.show(I18nManager.t('login.login_failed'));
                }
            },
            (msg) => {
                Toast.show(msg || I18nManager.t('login.login_failed'));
            }
        );
    }
};

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    Login.init();
});
