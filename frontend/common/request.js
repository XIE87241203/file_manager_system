/**
 * 用途说明：通用请求工具类，封装 fetch API，支持 Token 携带、自动跳转、以及可选的全局加载蒙版。
 */
const Request = {
    /**
     * 用途说明：显示全局加载蒙版。
     * 入参说明：无。
     * 返回值说明：无。
     */
    showLoading() {
        if (document.getElementById('global-loading-mask')) return;
        
        const mask = document.createElement('div');
        mask.id = 'global-loading-mask';
        mask.className = 'loading-mask';
        mask.innerHTML = `
            <div class="loading-spinner"></div>
            <div class="loading-text">正在处理中...</div>
        `;
        document.body.appendChild(mask);
    },

    /**
     * 用途说明：隐藏全局加载蒙版。
     * 入参说明：无。
     * 返回值说明：无。
     */
    hideLoading() {
        const mask = document.getElementById('global-loading-mask');
        if (mask) {
            mask.remove();
        }
    },

    /**
     * 用途说明：获取后端基础 API 地址。
     * 返回值说明：返回 API 基础路径字符串。
     */
    get baseUrl() {
        return sessionStorage.getItem('baseUrl') || 'http://127.0.0.1:5000';
    },

    /**
     * 用途说明：设置 Cookie。
     * 入参说明：name (键名), value (键值), hours (有效期小时)。
     */
    setCookie(name, value, hours) {
        let expires = "";
        if (hours) {
            const date = new Date();
            date.setTime(date.getTime() + (hours * 60 * 60 * 1000));
            expires = "; expires=" + date.toUTCString();
        }
        document.cookie = name + "=" + (value || "") + expires + "; path=/; SameSite=Lax";
    },

    /**
     * 用途说明：获取 Cookie。
     */
    getCookie(name) {
        const nameEQ = name + "=";
        const ca = document.cookie.split(';');
        for (let i = 0; i < ca.length; i++) {
            let c = ca[i];
            while (c.charAt(0) == ' ') c = c.substring(1, c.length);
            if (c.indexOf(nameEQ) == 0) return c.substring(nameEQ.length, c.length);
        }
        return null;
    },

    /**
     * 用途说明：删除 Cookie。
     */
    eraseCookie(name) {
        document.cookie = name + '=; Max-Age=-99999999; path=/;';
    },

    /**
     * 用途说明：基础请求实现方法。
     * 入参说明：
     *   - url: 接口路径。
     *   - options: fetch 原生配置。
     *   - showMask: 是否显示加载蒙版（默认 true）。
     * 返回值说明：Promise 解析后的响应数据对象。
     */
    async fetch(url, options = {}, showMask = true) {
        if (showMask) this.showLoading();

        const fullUrl = `${this.baseUrl}${url}`;
        const headers = { ...options.headers };

        if (options.body && !headers['Content-Type']) {
            headers['Content-Type'] = 'application/json';
        }

        const token = this.getCookie('token');
        if (token) {
            headers['Authorization'] = token;
        }

        const config = { ...options, headers };

        try {
            const response = await fetch(fullUrl, config);
            
            if (response.status === 401) {
                if (!url.includes('/api/login')) {
                    this.eraseCookie('token');
                    if (typeof Toast !== 'undefined') Toast.show('登录已过期，请重新登录');
                    
                    // 获取当前页面路径
                    const path = window.location.pathname;
                    let loginUrl = '../login/login.html';
                    
                    // 如果是在多层级目录（如 file_repository/duplicate_check/），需要根据层级调整
                    // 获取 frontend 后的路径层级
                    if (path.includes('/frontend/')) {
                        const subPath = path.split('/frontend/')[1];
                        const depth = subPath.split('/').filter(p => p && !p.endsWith('.html')).length;
                        loginUrl = '../'.repeat(depth) + 'login/login.html';
                    }

                    setTimeout(() => { window.location.href = loginUrl; }, 1500);
                    if (showMask) this.hideLoading();
                    return Promise.reject({ message: '登录已过期' });
                }
            }

            const contentType = response.headers.get("content-type");
            let result = (contentType && contentType.includes("application/json")) 
                ? await response.json() 
                : { message: await response.text() };
            
            if (!response.ok) {
                if (showMask) this.hideLoading();
                return Promise.reject(result);
            }
            
            if (showMask) this.hideLoading();
            return result;
        } catch (error) {
            if (showMask) this.hideLoading();
            console.error('API 请求失败:', error);
            throw error;
        }
    },

    /**
     * 用途说明：执行 GET 请求。
     * 入参说明：url (路径), headers (请求头), showMask (是否显隐蒙版)。
     */
    get(url, headers = {}, showMask = true) {
        return this.fetch(url, { method: 'GET', headers }, showMask);
    },

    /**
     * 用途说明：执行 POST 请求。
     * 入参说明：url (路径), data (请求体), headers (请求头), showMask (是否显隐蒙版)。
     */
    post(url, data = {}, headers = {}, showMask = true) {
        return this.fetch(url, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(data)
        }, showMask);
    }
};
