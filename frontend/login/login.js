/**
 * 用途：登录页逻辑管理，处理用户登录、表单验证及环境初始化
 */
const Login = {
    /**
     * 用途：初始化登录页面，绑定事件
     */
    init() {
        // 清空认证信息
        Request.eraseCookie('token');
        sessionStorage.removeItem('username');

        // 绑定回车键事件
        this.bindEvents();
    },

    /**
     * 用途：为输入框绑定回车提交事件
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
     * 用途：获取表单数据并执行登录逻辑
     */
    async handleLogin() {
        const username = document.getElementById('username').value.trim();
        const password = document.getElementById('password').value;

        // 表单校验
        if (!username || !password) {
            Toast.show("请输入用户名和密码");
            return;
        }

        // 自动使用当前页面 origin 作为 API 基础地址
        const apiUrl = window.location.origin;
        sessionStorage.setItem('baseUrl', apiUrl);

        // 前端 SHA-256 加密
        const passwordHash = CryptoJS.SHA256(password).toString();

        try {
            // 使用封装的 Request 工具发起 POST 请求
            const result = await Request.post('/api/login', {
                username: username,
                password_hash: passwordHash
            });

            // 登录成功处理
            if (result.status === 'success' && result.data && result.data.token) {
                // 保存 Token (有效期 6 小时)
                Request.setCookie('token', result.data.token, 6);
                // 缓存用户名
                sessionStorage.setItem('username', username);
                
                window.location.href = '../home/home.html';
            } else {
                Toast.show(result.message || "登录失败");
            }
        } catch (error) {
            console.error('登录请求异常:', error);
            Toast.show(error.message || "无法连接到后端服务器，请检查服务是否启动");
        }
    }
};

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    Login.init();
});
