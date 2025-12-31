/**
 * 用途：处理登录表单提交，执行前端哈希并调用后端 API，登录成功后跳转到首页
 * 入参说明：无（直接从 DOM 元素获取输入）
 * 返回值说明：无（异步处理跳转或错误提示）
 */
async function handleLogin() {
    const apiUrl = document.getElementById('apiUrl').value.trim();
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const messageDiv = document.getElementById('message');

    if (!apiUrl) {
        messageDiv.innerText = "请输入后端 API 地址";
        return;
    }
    if (!username || !password) {
        messageDiv.innerText = "请输入用户名和密码";
        return;
    }

    // 将 API 地址保存到 sessionStorage，供全局 Request 工具类使用
    sessionStorage.setItem('baseUrl', apiUrl);

    // 1. 前端 SHA-256 加密，防止明文传输
    const passwordHash = CryptoJS.SHA256(password).toString();

    try {
        // 2. 使用填写的 API 地址进行登录请求
        const response = await fetch(`${apiUrl}/api/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                username: username,
                password_hash: passwordHash
            })
        });

        const result = await response.json();

        if (response.ok) {
            // 3. 保存返回的 Token 到 Cookies 中 (有效期 6 小时)
            // 后端 success_response 会将数据封装在 data 字段中
            if (result.data && result.data.token) {
                const token = result.data.token;
                // 注意：Request 对象是在 common/request.js 中定义的
                // 登录页必须在 HTML 中引入 request.js 才能使用该方法
                if (typeof Request !== 'undefined') {
                    Request.setCookie('token', token, 6);
                } else {
                    // 如果由于某种原因 Request 未加载，作为兜底
                    document.cookie = `token=${token}; path=/; max-age=${6*3600}; SameSite=Lax`;
                }
//                // 登录成功后自动跳转到 home 页面
                window.location.href = '../home/home.html';
            }
        } else {
            messageDiv.innerText = result.message || "登录失败";
        }
    } catch (error) {
        console.error('API 请求失败:', error);
        messageDiv.innerText = "无法连接到后端服务器，请检查地址是否正确及后端是否启动";
    }
}

/**
 * 用途：页面加载时的初始化操作，包括绑定事件和清空 Token
 * 入参说明：无
 * 返回值说明：无
 */
document.addEventListener('DOMContentLoaded', () => {
    // 按照规则要求：进入登录页面时清空 Cookies 中的 token
    if (typeof Request !== 'undefined') {
        Request.eraseCookie('token');
    } else {
        document.cookie = 'token=; Max-Age=-99999999; path=/;';
    }

    const inputs = ['apiUrl', 'username', 'password'];
    inputs.forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            element.addEventListener('keypress', (event) => {
                if (event.key === 'Enter') {
                    handleLogin();
                }
            });
        }
    });
});
