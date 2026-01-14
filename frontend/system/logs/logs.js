/**
 * 用途说明：运行日志页面逻辑处理，实现日志的自动轮询、手动刷新、等级与关键词筛选，以及不同级别日志的着色渲染。
 */

// --- 状态管理 ---
const State = {
    refreshIntervalSec: 3, // 默认 3 秒刷新一次
    logLines: 200,         // 默认读取末尾 200 行
    logLevel: 'ALL',       // 默认显示全部等级
    logKeyword: '',        // 搜索关键词
    excludeApi: true,      // 是否过滤 API 日志
    isAutoRefresh: true,   // 是否处于自动刷新状态
    refreshTimer: null,    // 存储 setInterval 的 ID
    logContentElement: null
};

// --- UI 控制模块 ---
const UIController = {
    /**
     * 用途说明：初始化 UI 元素缓存及公用头部
     */
    init() {
        UIComponents.initHeader('运行日志');
        State.logContentElement = document.getElementById('log-content');
        
        this.bindEvents();
        this.updateAutoRefreshUI();
    },

    /**
     * 用途说明：绑定控制栏事件
     */
    bindEvents() {
        const intervalInput = document.getElementById('refresh-interval');
        const linesSelect = document.getElementById('log-lines');
        const levelSelect = document.getElementById('log-level');
        const keywordInput = document.getElementById('log-keyword');
        const excludeApiCheckbox = document.getElementById('exclude-api');
        const toggleBtn = document.getElementById('btn-toggle-auto');
        const refreshBtn = document.getElementById('btn-manual-refresh');

        // 监听间隔变化
        intervalInput.onchange = (e) => {
            let val = parseInt(e.target.value);
            if (isNaN(val) || val < 1) val = 1;
            if (val > 60) val = 60;
            e.target.value = val;
            State.refreshIntervalSec = val;
            if (State.isAutoRefresh) App.restartAutoRefresh();
        };

        // 监听行数变化
        linesSelect.onchange = (e) => {
            State.logLines = parseInt(e.target.value);
            App.loadLogs();
        };

        // 监听等级变化
        levelSelect.onchange = (e) => {
            State.logLevel = e.target.value;
            App.loadLogs();
        };

        // 监听 API 过滤复选框
        excludeApiCheckbox.onchange = (e) => {
            State.excludeApi = e.target.checked;
            App.loadLogs();
        };

        // 监听关键词变化（防抖处理或回车触发）
        keywordInput.onkeypress = (e) => {
            if (e.key === 'Enter') {
                State.logKeyword = keywordInput.value.trim();
                App.loadLogs();
            }
        };
        keywordInput.onblur = () => {
            State.logKeyword = keywordInput.value.trim();
            App.loadLogs();
        };

        // 切换自动刷新
        toggleBtn.onclick = () => {
            State.isAutoRefresh = !State.isAutoRefresh;
            this.updateAutoRefreshUI();
            if (State.isAutoRefresh) App.startAutoRefresh();
            else App.stopAutoRefresh();
        };

        // 手动刷新
        refreshBtn.onclick = () => App.loadLogs();
    },

    /**
     * 用途说明：更新自动刷新相关的按钮文字和状态显示
     */
    updateAutoRefreshUI() {
        const toggleBtn = document.getElementById('btn-toggle-auto');
        const statusText = document.getElementById('status-text');
        
        if (State.isAutoRefresh) {
            toggleBtn.textContent = '停止自动刷新';
            toggleBtn.className = 'right-btn btn-text-danger';
            statusText.textContent = `自动监控中 (${State.refreshIntervalSec}s)...`;
            statusText.style.color = '#1a73e8';
        } else {
            toggleBtn.textContent = '启动自动刷新';
            toggleBtn.className = 'right-btn';
            statusText.textContent = '已停止刷新';
            statusText.style.color = '#5f6368';
        }
    },

    /**
     * 用途说明：将日志文本渲染到展示区，并根据关键词着色
     * 入参说明：logs (Array): 日志行列表
     */
    renderLogs(logs) {
        const container = State.logContentElement;
        
        if (!logs || logs.length === 0) {
            container.innerHTML = '<div class="log-line">未找到匹配的日志内容</div>';
            return;
        }

        // 记录当前是否在底部，以便判断是否自动滚动
        const isAtBottom = (container.scrollHeight - container.clientHeight) <= (container.scrollTop + 50);

        container.innerHTML = logs.map(line => this.formatLogLine(line)).join('');

        // 如果之前就在底部，则新的日志进来后继续保持在底部
        if (isAtBottom) {
            container.scrollTop = container.scrollHeight;
        }
    },

    /**
     * 用途说明：对单行日志进行解析和着色
     * 入参说明：line (str): 原始日志行文本
     * 返回值说明：str - HTML 字符串
     */
    formatLogLine(line) {
        if (!line.trim()) return '';

        let levelClass = '';
        if (line.includes(' - INFO - ')) levelClass = 'log-info';
        else if (line.includes(' - DEBUG - ')) levelClass = 'log-debug';
        else if (line.includes(' - ERROR - ')) levelClass = 'log-error';
        else if (line.includes(' - WARNING - ')) levelClass = 'log-warn';

        // 简单处理时间戳显色
        const timeMatch = line.match(/^(\d{4}\/\d{2}\/\d{2}-\d{2}:\d{2}:\d{2}:\d{3})/);
        if (timeMatch) {
            const timeStr = timeMatch[1];
            const rest = line.substring(timeStr.length);
            return `<span class="log-line ${levelClass}"><span class="log-time">${timeStr}</span>${this.escapeHtml(rest)}</span>`;
        }

        return `<span class="log-line ${levelClass}">${this.escapeHtml(line)}</span>`;
    },

    /**
     * 用途说明：转义 HTML 字符
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};

// --- API 交互模块 ---
const LogsAPI = {
    /**
     * 用途说明：从后端获取经过筛选的最新日志
     */
    async fetchLogs(params) {
        const query = new URLSearchParams(params).toString();
        return await Request.get(`/api/system/logs?${query}`, {}, false);
    }
};

// --- 应用逻辑主入口 ---
const App = {
    init() {
        UIController.init();
        this.loadLogs();
        if (State.isAutoRefresh) this.startAutoRefresh();
    },

    /**
     * 用途说明：执行一次日志加载
     */
    async loadLogs() {
        const params = {
            lines: State.logLines,
            level: State.logLevel,
            exclude_api: State.excludeApi
        };
        if (State.logKeyword) params.keyword = State.logKeyword;

        const response = await LogsAPI.fetchLogs(params);
        if (response.status === 'success') {
            UIController.renderLogs(response.data.logs);
        } else {
            console.error('加载日志失败:', response.message);
        }
    },

    /**
     * 用途说明：启动定时器执行自动刷新
     */
    startAutoRefresh() {
        this.stopAutoRefresh();
        State.refreshTimer = setInterval(() => this.loadLogs(), State.refreshIntervalSec * 1000);
    },

    /**
     * 用途说明：停止定时器
     */
    stopAutoRefresh() {
        if (State.refreshTimer) {
            clearInterval(State.refreshTimer);
            State.refreshTimer = null;
        }
    },

    /**
     * 用途说明：重启定时器
     */
    restartAutoRefresh() {
        this.stopAutoRefresh();
        this.startAutoRefresh();
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
