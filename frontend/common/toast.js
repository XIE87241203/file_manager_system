/**
 * 用途：公用 Toast 提示组件，支持自动销毁和多消息叠加
 */
const Toast = {
    /**
     * 用途：显示 Toast 提示消息
     * 入参说明：
     *   - message: 提示文本内容
     *   - duration: 显示时长（毫秒），默认为 3000ms
     * 返回值说明：无
     */
    show(message, duration = 3000) {
        // 1. 获取或创建容器
        let container = document.querySelector('.toast-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'toast-container';
            document.body.appendChild(container);
        }

        // 2. 创建消息条目
        const toastItem = document.createElement('div');
        toastItem.className = 'toast-item';
        toastItem.innerText = message;
        container.appendChild(toastItem);

        // 3. 设定定时器自动移除
        // 注意：动画时间在 common.css 中定义，此处需配合移除 DOM
        setTimeout(() => {
            if (toastItem.parentNode) {
                // 执行渐隐动画或直接移除
                toastItem.style.opacity = '0';
                setTimeout(() => {
                    if (toastItem.parentNode) {
                        container.removeChild(toastItem);
                    }
                    // 如果容器空了，则移除容器
                    if (container.childNodes.length === 0 && container.parentNode) {
                        document.body.removeChild(container);
                    }
                }, 300); // 给一点渐隐缓冲
            }
        }, duration);
    }
};
