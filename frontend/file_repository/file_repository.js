/**
 * 用途说明：文件仓库页面逻辑处理，负责文件列表展示、分页、排序、搜索以及异步扫描任务的生命周期管理。
 */

// --- 状态管理 ---
const State = {
    page: 1,
    limit: 15,
    sortBy: 'scan_time',
    order: 'DESC',
    search: '',
    searchHistory: false,
    scanInterval: null
};

// --- UI 控制模块 ---
const UIController = {
    elements: {},

    /**
     * 用途说明：初始化 UI 控制器，缓存常用的 DOM 元素
     * 入参说明：无
     * 返回值说明：无
     */
    init() {
        this.elements = {
            tableBody: document.getElementById('file-list-body'),
            pageInfo: document.getElementById('page-info'),
            prevBtn: document.getElementById('btn-prev-page'),
            nextBtn: document.getElementById('btn-next-page'),
            scanBtn: document.getElementById('btn-scan'),
            mainContent: document.getElementById('repo-main-content'),
            searchInput: document.getElementById('search-input'),
            searchHistoryCheckbox: document.getElementById('search-history-checkbox'),
            backBtn: document.getElementById('nav-back-btn'),
            searchBtn: document.getElementById('search-btn'),
            duplicateBtn: document.getElementById('btn-duplicate-check'),
            sortableHeaders: document.querySelectorAll('th.sortable')
        };
    },

    /**
     * 用途说明：渲染文件表格内容
     * 入参说明：list (Array) - 文件列表数据
     * 返回值说明：无
     */
    renderTable(list) {
        const { tableBody } = this.elements;
        tableBody.innerHTML = '';

        if (!list || list.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding: 100px; color: #9aa0a6;">暂无索引文件</td></tr>';
            return;
        }

        list.forEach(file => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td title="${file.file_name}">${file.file_name}</td>
                <td title="${file.file_path}">${file.file_path}</td>
                <td><code>${file.file_md5}</code></td>
                <td>${file.scan_time}</td>
            `;
            tableBody.appendChild(tr);
        });
    },

    /**
     * 用途说明：更新分页控件显示状态
     * 入参说明：total (Number) - 总记录数，page (Number) - 当前页码
     * 返回值说明：无
     */
    updatePagination(total, page) {
        const totalPages = Math.ceil(total / State.limit) || 1;
        this.elements.pageInfo.textContent = `第 ${page} / ${totalPages} 页 (共 ${total} 条)`;
        this.elements.prevBtn.disabled = (page <= 1);
        this.elements.nextBtn.disabled = (page >= totalPages);
    },

    /**
     * 用途说明：更新表头排序图标和样式
     * 入参说明：field (String) - 排序字段，order (String) - 排序顺序
     * 返回值说明：无
     */
    updateSortUI(field, order) {
        this.elements.sortableHeaders.forEach(th => {
            th.classList.remove('sort-asc', 'sort-desc');
            if (th.getAttribute('data-field') === field) {
                th.classList.add(order === 'ASC' ? 'sort-asc' : 'sort-desc');
            }
        });
    },

    /**
     * 用途说明：切换扫描状态下的 UI 显示
     * 入参说明：isScanning (Boolean) - 是否正在扫描
     * 返回值说明：无
     */
    toggleScanUI(isScanning) {
        const { mainContent, scanBtn } = this.elements;
        if (isScanning) {
            mainContent.style.visibility = 'hidden';
            if (scanBtn) {
                scanBtn.textContent = '停止索引';
                scanBtn.className = 'btn-text-danger'; // 使用公共红色文字按钮样式
            }
        } else {
            mainContent.style.visibility = 'visible';
            if (scanBtn) {
                scanBtn.textContent = '建立索引';
                scanBtn.className = 'right-btn';
            }
        }
    },

    /**
     * 用途说明：更新扫描进度条
     * 入参说明：progress (Object) - 进度数据
     * 返回值说明：无
     */
    updateProgress(progress) {
        const percent = progress.total > 0 ? Math.round((progress.current / progress.total) * 100) : 0;
        const text = `进度: ${percent}% (${progress.current}/${progress.total}) - ${progress.current_file}`;
        UIComponents.updateProgressBar('.repo-container', percent, text);
    }
};

// --- API 交互模块 ---
const RepositoryAPI = {
    /**
     * 用途说明：获取文件列表
     * 入参说明：params (Object) - 查询参数
     * 返回值说明：Promise - 请求响应结果
     */
    async getFileList(params) {
        const query = new URLSearchParams(params).toString();
        return await Request.get(`/api/file_repository/list?${query}`, {}, true);
    },

    /**
     * 用途说明：启动扫描任务
     * 入参说明：无
     * 返回值说明：Promise - 请求响应结果
     */
    async startScan() {
        return await Request.post('/api/file_repository/scan', {}, {}, true);
    },

    /**
     * 用途说明：停止扫描任务
     * 入参说明：无
     * 返回值说明：Promise - 请求响应结果
     */
    async stopScan() {
        return await Request.post('/api/file_repository/stop', {}, {}, true);
    },

    /**
     * 用途说明：获取扫描进度
     * 入参说明：无
     * 返回值说明：Promise - 请求响应结果
     */
    async getProgress() {
        return await Request.get('/api/file_repository/progress', {}, false);
    }
};

// --- 应用逻辑主入口 ---
const App = {
    /**
     * 用途说明：初始化应用
     * 入参说明：无
     * 返回值说明：无
     */
    init() {
        UIController.init();
        this.bindEvents();
        this.loadFileList();
        this.checkScanStatus();
    },

    /**
     * 用途说明：绑定事件监听
     * 入参说明：无
     * 返回值说明：无
     */
    bindEvents() {
        const { prevBtn, nextBtn, scanBtn, searchInput, searchBtn, searchHistoryCheckbox, backBtn, duplicateBtn, sortableHeaders } = UIController.elements;

        // 分页逻辑
        if (prevBtn) prevBtn.onclick = () => { if (State.page > 1) { State.page--; this.loadFileList(); } };
        if (nextBtn) nextBtn.onclick = () => { State.page++; this.loadFileList(); };

        // 搜索逻辑
        const onSearch = () => {
            State.search = searchInput.value.trim();
            State.searchHistory = searchHistoryCheckbox.checked;
            State.page = 1;
            this.loadFileList();
        };
        if (searchBtn) searchBtn.onclick = onSearch;
        if (searchInput) searchInput.onkeypress = (e) => { if (e.key === 'Enter') onSearch(); };
        if (searchHistoryCheckbox) searchHistoryCheckbox.onchange = onSearch;

        // 索引任务逻辑
        if (scanBtn) {
            scanBtn.onclick = () => {
                if (scanBtn.textContent === '建立索引') this.handleStartScan();
                else this.handleStopScan();
            };
        }

        // 表头排序逻辑
        sortableHeaders.forEach(th => {
            th.onclick = () => {
                const field = th.getAttribute('data-field');
                if (State.sortBy === field) {
                    State.order = (State.order === 'ASC' ? 'DESC' : 'ASC');
                } else {
                    State.sortBy = field;
                    State.order = 'DESC';
                }
                State.page = 1;
                this.loadFileList();
            };
        });

        // 导航与跳转
        if (backBtn) backBtn.onclick = () => window.history.back();
        if (duplicateBtn) {
            duplicateBtn.onclick = () => {
                window.location.href = './duplicate_check/duplicate_check.html';
            };
        }
    },

    /**
     * 用途说明：加载文件列表数据并更新 UI
     * 入参说明：无
     * 返回值说明：无
     */
    async loadFileList() {
        try {
            const response = await RepositoryAPI.getFileList({
                page: State.page,
                limit: State.limit,
                sort_by: State.sortBy,
                order: State.order,
                search: State.search,
                search_history: State.searchHistory
            });
            if (response.status === 'success') {
                UIController.renderTable(response.data.list);
                UIController.updatePagination(response.data.total, State.page);
                UIController.updateSortUI(State.sortBy, State.order);
            }
        } catch (error) {
            console.error('加载文件列表失败:', error);
        }
    },

    /**
     * 用途说明：触发启动扫描任务
     * 入参说明：无
     * 返回值说明：无
     */
    async handleStartScan() {
        try {
            const response = await RepositoryAPI.startScan();
            if (response.status === 'success') {
                Toast.show('索引任务已启动');
                UIComponents.showProgressBar('.repo-container', '正在准备建立索引...');
                this.enterScanningState();
            } else {
                Toast.show(response.msg);
            }
        } catch (error) {
            Toast.show('启动失败');
        }
    },

    /**
     * 用途说明：触发停止扫描任务
     * 入参说明：无
     * 返回值说明：无
     */
    async handleStopScan() {
        if (!confirm('确定要终止当前的索引任务吗？')) return;
        try {
            await RepositoryAPI.stopScan();
            Toast.show('正在停止任务...');
        } catch (error) {
            Toast.show('请求停止失败');
        }
    },

    /**
     * 用途说明：进入扫描监控状态，开启定时轮询
     * 入参说明：无
     * 返回值说明：无
     */
    enterScanningState() {
        UIController.toggleScanUI(true);
        if (!State.scanInterval) {
            State.scanInterval = setInterval(() => this.checkScanStatus(), 2000);
        }
    },

    /**
     * 用途说明：主动检查扫描任务进度
     * 入参说明：无
     * 返回值说明：无
     */
    async checkScanStatus() {
        try {
            const response = await RepositoryAPI.getProgress();
            if (response && response.status === 'success') {
                const { status, progress } = response.data;
                
                if (status === 'scanning') {
                    if (!State.scanInterval) {
                        UIComponents.showProgressBar('.repo-container', '正在建立索引...');
                        this.enterScanningState();
                    }
                    UIController.updateProgress(progress);
                } else {
                    if (State.scanInterval) {
                        clearInterval(State.scanInterval);
                        State.scanInterval = null;
                    }
                    UIController.toggleScanUI(false);
                    UIComponents.hideProgressBar('.repo-container');
                    
                    if (status === 'completed') {
                        this.loadFileList();
                    }
                }
            }
        } catch (error) {
            console.error('获取进度失败:', error);
        }
    }
};

// 页面加载完成后启动应用
document.addEventListener('DOMContentLoaded', () => App.init());
