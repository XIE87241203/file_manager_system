/**
 * 用途说明：通用请求工具类，封装 fetch API，支持 Token 携带、自动跳转、以及可选的全局加载蒙版。
 */
const Request = {
    /**
     * 用途说明：显示全局加载蒙版。
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
     * 逻辑说明：优先从 sessionStorage 获取，若无则使用当前页面的 origin。
     */
    get baseUrl() {
        return sessionStorage.getItem('baseUrl') || window.location.origin;
    },

    /**
     * 用途说明：设置 Cookie。
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
     */
    async fetch(url, options = {}, showMask = true) {
        if (showMask) this.showLoading();

        // 拼接完整 URL
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
                    
                    // 同端口环境下，直接跳转到 /login/login.html
                    setTimeout(() => { window.location.href = '/login/login.html'; }, 1500);
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

    get(url, headers = {}, showMask = true) {
        return this.fetch(url, { method: 'GET', headers }, showMask);
    },

    post(url, data = {}, headers = {}, showMask = true) {
        return this.fetch(url, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(data)
        }, showMask);
    }
};
