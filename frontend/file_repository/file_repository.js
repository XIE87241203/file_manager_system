/**
 * 用途说明：文件仓库页面逻辑处理，负责文件列表展示、分页、排序、搜索以及异步任务（索引、缩略图）的生命周期管理。
 */

// --- 状态管理 ---
const State = {
    page: 1,
    limit: 20,
    sortBy: 'scan_time',
    order: 'DESC',
    search: '',
    searchHistory: false,
    scanInterval: null,
    thumbnailInterval: null,
    selectedPaths: new Set(), // 存储选中文件的路径
    settings: null // 存储系统设置
};

// --- UI 控制模块 ---
const UIController = {
    elements: {},

    /**
     * 用途说明：初始化 UI 控制器，缓存常用的 DOM 元素，并动态处理页面内容避让
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
            sortableHeaders: document.querySelectorAll('th.sortable'),
            selectAllCheckbox: document.getElementById('select-all-checkbox'),
            deleteSelectedBtn: document.getElementById('btn-delete-selected'),
            thumbnailBtn: document.getElementById('btn-thumbnail'),
            thumbnailProgressText: document.getElementById('thumbnail-progress-text')
        };

        // 动态避开头部高度：不再依赖 CSS 硬编码，确保布局精准
        const repoContainer = document.querySelector('.repo-container');
        if (repoContainer) {
            repoContainer.style.marginTop = UIComponents.getToolbarHeight() + 'px';
        }
    },

    /**
     * 用途说明：渲染文件表格内容
     * 入参说明：list (Array) - 文件列表数据
     * 返回值说明：无
     */
    renderTable(list) {
        const { tableBody, selectAllCheckbox } = this.elements;
        tableBody.innerHTML = '';
        
        // 重置并根据模式控制全选列显示
        if (selectAllCheckbox) {
            selectAllCheckbox.checked = false;
            // 历史库不支持删除，隐藏全选列头
            selectAllCheckbox.parentElement.style.display = State.searchHistory ? 'none' : 'table-cell';
        }

        if (!list || list.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="${State.searchHistory ? 4 : 5}" style="text-align:center; padding: 100px; color: #9aa0a6;">暂无索引文件</td></tr>`;
            return;
        }

        list.forEach(file => {
            const isChecked = State.selectedPaths.has(file.file_path);
            const tr = document.createElement('tr');
            tr.setAttribute('data-path', file.file_path);
            tr.setAttribute('data-thumbnail', file.thumbnail_path || '');
            if (isChecked) tr.classList.add('selected-row');
            
            let html = `
                <td title="${file.file_name}">${file.file_name}</td>
                <td title="${file.file_path}">${file.file_path}</td>
                <td><code>${file.file_md5}</code></td>
                <td>${file.scan_time}</td>
            `;

            // 非历史库模式下展示复选框列
            if (!State.searchHistory) {
                html += `
                    <td style="text-align: center;">
                        <input type="checkbox" class="file-checkbox" data-path="${file.file_path}" ${isChecked ? 'checked' : ''}>
                    </td>
                `;
            }

            tr.innerHTML = html;
            
            // 绑定悬停预览事件 (使用通用 UI 组件)
            if (State.settings && State.settings.file_repository.quick_view_thumbnail) {
                tr.addEventListener('mouseenter', (e) => UIComponents.showQuickPreview(e, file.thumbnail_path));
                tr.addEventListener('mousemove', (e) => UIComponents.moveQuickPreview(e));
                tr.addEventListener('mouseleave', () => UIComponents.hideQuickPreview());
            }

            tableBody.appendChild(tr);
        });
        
        this.updateDeleteButtonVisibility();
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
                scanBtn.className = 'right-btn btn-text-danger';
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
        UIComponents.renderProgress('.repo-container', progress);
    },

    /**
     * 用途说明：根据选中状态更新删除按钮可见性
     * 入参说明：无
     * 返回值说明：无
     */
    updateDeleteButtonVisibility() {
        const { deleteSelectedBtn } = this.elements;
        if (!deleteSelectedBtn) return;
        
        // 历史库模式下禁止删除，强制隐藏按钮
        if (State.searchHistory) {
            deleteSelectedBtn.style.display = 'none';
            return;
        }

        if (State.selectedPaths.size > 0) {
            deleteSelectedBtn.style.display = 'block';
            deleteSelectedBtn.textContent = `删除选中 (${State.selectedPaths.size})`;
        } else {
            deleteSelectedBtn.style.display = 'none';
        }
    },

    /**
     * 用途说明：切换缩略图生成状态下的 UI 显示
     * 入参说明：isGenerating (Boolean) - 是否正在生成
     * 返回值说明：无
     */
    toggleThumbnailUI(isGenerating) {
        const { thumbnailBtn, thumbnailProgressText } = this.elements;
        if (!thumbnailBtn) return;

        if (isGenerating) {
            thumbnailBtn.textContent = '停止生成';
            thumbnailBtn.className = 'btn-text-danger-small';
            thumbnailProgressText.style.display = 'inline';
        } else {
            thumbnailBtn.textContent = '生成缩略图';
            thumbnailBtn.className = 'btn-secondary-small';
            thumbnailProgressText.style.display = 'none';
        }
    },

    /**
     * 用途说明：更新缩略图生成进度文案
     * 入参说明：progress (Object) - 进度数据
     * 返回值说明：无
     */
    updateThumbnailProgress(progress) {
        const { thumbnailProgressText } = this.elements;
        if (!thumbnailProgressText || !progress) return;
        
        thumbnailProgressText.textContent = progress.message || '';
    }
};

// --- API 交互模块 ---
const RepositoryAPI = {
    /**
     * 用途说明：获取文件列表
     * 入参说明：params (Object) - 查询参数，包含 page, limit, sort_by, order, search, search_history
     * 返回值说明：Promise - 请求响应结果，data 字段结构为 PaginationResult:
     *   {
     *     total: number,           // 总记录数
     *     page: number,            // 当前页码
     *     limit: number,           // 每页限制数
     *     sort_by: string,         // 排序字段
     *     order: string,           // 排序方向 (ASC/DESC)
     *     list: Array<Object>      // 文件对象列表 (FileIndex 或 HistoryFileIndex)
     *   }
     */
    async getFileList(params) {
        const query = new URLSearchParams(params).toString();
        return await Request.get(`/api/file_repository/list?${query}`, {}, true);
    },

    /**
     * 用途说明：批量删除文件
     * 入参说明：filePaths (Array) - 文件路径列表
     * 返回值说明：Promise - 请求响应结果
     */
    async deleteFiles(filePaths) {
        return await Request.post('/api/file_repository/delete', { file_paths: filePaths }, {}, true);
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
    },

    /**
     * 用途说明：启动缩略图生成任务
     * 入参说明：rebuildAll (Boolean) - 是否重构所有缩略图
     * 返回值说明：Promise - 请求响应结果
     */
    async startThumbnailGeneration(rebuildAll = false) {
        return await Request.post('/api/file_repository/thumbnail/start', { rebuild_all: rebuildAll }, {}, true);
    },

    /**
     * 用途说明：停止缩略图生成任务
     * 入参说明：无
     * 返回值说明：Promise - 请求响应结果
     */
    async stopThumbnailGeneration() {
        return await Request.post('/api/file_repository/thumbnail/stop', {}, {}, true);
    },

    /**
     * 用途说明：获取缩略图生成进度
     * 入参说明：无
     * 返回值说明：Promise - 请求响应结果
     */
    async getThumbnailProgress() {
        return await Request.get('/api/file_repository/thumbnail/progress', {}, false);
    }
};

// --- 应用逻辑主入口 ---
const App = {
    /**
     * 用途说明：初始化应用
     * 入参说明：无
     * 返回值说明：无
     */
    async init() {
        UIController.init();
        this.bindEvents();
        await this.loadSettings();
        this.loadFileList();
        this.checkScanStatus();
        this.checkThumbnailStatus();
    },

    /**
     * 用途说明：从后端加载设置
     * 入参说明：无
     * 返回值说明：无
     */
    async loadSettings() {
        try {
            const response = await Request.get('/api/setting/get');
            if (response.status === 'success') {
                State.settings = response.data;
            }
        } catch (error) {
            console.error('加载设置失败:', error);
        }
    },

    /**
     * 用途说明：绑定事件监听
     * 入参说明：无
     * 返回值说明：无
     */
    bindEvents() {
        const { 
            prevBtn, nextBtn, scanBtn, searchInput, searchBtn, 
            searchHistoryCheckbox, backBtn, duplicateBtn, sortableHeaders,
            selectAllCheckbox, tableBody, deleteSelectedBtn, thumbnailBtn
        } = UIController.elements;

        // 分页逻辑
        if (prevBtn) prevBtn.onclick = () => { if (State.page > 1) { State.page--; this.loadFileList(); } };
        if (nextBtn) nextBtn.onclick = () => { State.page++; this.loadFileList(); };

        // 搜索逻辑
        const onSearch = () => {
            State.search = searchInput.value.trim();
            State.searchHistory = searchHistoryCheckbox.checked;
            State.page = 1;
            State.selectedPaths.clear(); // 搜索时清空选中
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

        // 缩略图生成逻辑
        if (thumbnailBtn) {
            thumbnailBtn.onclick = () => {
                if (thumbnailBtn.textContent === '生成缩略图') this.confirmStartThumbnail();
                else this.handleStopThumbnail();
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

        // 全选/取消全选逻辑
        if (selectAllCheckbox) {
            selectAllCheckbox.onchange = (e) => {
                if (State.searchHistory) return; // 历史库不支持选择
                
                const isChecked = e.target.checked;
                const checkboxes = tableBody.querySelectorAll('.file-checkbox');
                checkboxes.forEach(cb => {
                    cb.checked = isChecked;
                    const path = cb.getAttribute('data-path');
                    const row = cb.closest('tr');
                    if (isChecked) {
                        State.selectedPaths.add(path);
                        row.classList.add('selected-row');
                    } else {
                        State.selectedPaths.delete(path);
                        row.classList.remove('selected-row');
                    }
                });
                UIController.updateDeleteButtonVisibility();
            };
        }

        // 行点击勾选逻辑（包含复选框自身点击的处理）
        if (tableBody) {
            tableBody.addEventListener('click', (e) => {
                if (State.searchHistory) return; // 历史库不支持选择
                
                const tr = e.target.closest('tr');
                if (!tr) return;
                
                const path = tr.getAttribute('data-path');
                if (!path) return;

                const checkbox = tr.querySelector('.file-checkbox');
                let isChecked;
                
                if (e.target.classList.contains('file-checkbox')) {
                    isChecked = e.target.checked;
                } else {
                    isChecked = !checkbox.checked;
                    checkbox.checked = isChecked;
                }

                if (isChecked) {
                    State.selectedPaths.add(path);
                    tr.classList.add('selected-row');
                } else {
                    State.selectedPaths.delete(path);
                    tr.classList.remove('selected-row');
                    if (selectAllCheckbox) selectAllCheckbox.checked = false;
                }
                UIController.updateDeleteButtonVisibility();
            });
        }

        // 批量删除逻辑
        if (deleteSelectedBtn) {
            deleteSelectedBtn.onclick = () => this.handleBatchDelete();
        }

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
     * 用途说明：执行批量删除操作
     * 入参说明：无
     * 返回值说明：无
     */
    async handleBatchDelete() {
        const count = State.selectedPaths.size;
        if (count === 0) return;
        
        UIComponents.showConfirmModal({
            title: '确认删除',
            message: `确定要从磁盘及数据库中删除选中的 ${count} 个文件吗？此操作不可逆！`,
            confirmText: '确定删除',
            onConfirm: async () => {
                try {
                    const paths = Array.from(State.selectedPaths);
                    const response = await RepositoryAPI.deleteFiles(paths);
                    
                    if (response.status === 'success') {
                        Toast.show(response.message);
                        State.selectedPaths.clear();
                        this.loadFileList();
                    } else {
                        Toast.show('删除失败: ' + (response.message || '未知错误'));
                    }
                } catch (error) {
                    Toast.show('请求删除出错');
                }
            }
        });
    },

    /**
     * 用途说明：触发启动扫描任务
     * 入参说明：无
     * 返回值说明：无
     */
    async handleStartScan() {
        try {
            const response = await RepositoryAPI.startScan({});
            if (response.status === 'success') {
                Toast.show('索引任务已启动');
                UIComponents.showProgressBar('.repo-container', '正在准备建立索引...');
                this.enterScanningState();
            } else {
                Toast.show(response.message);
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
        UIComponents.showConfirmModal({
            title: '停止确认',
            message: '确定要终止当前的索引任务吗？',
            confirmText: '停止',
            onConfirm: async () => {
                try {
                    await RepositoryAPI.stopScan();
                    Toast.show('正在停止任务...');
                } catch (error) {
                    Toast.show('请求停止失败');
                }
            }
        });
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
                
                if (status === ProgressStatus.PROCESSING) {
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
                    
                    if (status === ProgressStatus.COMPLETED) {
                        this.loadFileList();
                    }
                }
            }
        } catch (error) {
            console.error('获取进度失败:', error);
        }
    },

    /**
     * 用途说明：显示缩略图生成确认弹窗
     * 入参说明：无
     * 返回值说明：无
     */
    confirmStartThumbnail() {
        UIComponents.showConfirmModal({
            title: '缩略图生成确认',
            message: '即将对仓库中的媒体文件生成缩略图。',
            confirmText: '开始生成',
            checkbox: {
                label: '仅生成缺失缩略图',
                checked: true
            },
            onConfirm: (onlyMissing) => {
                this.handleStartThumbnail(!onlyMissing); // rebuild_all = !onlyMissing
            }
        });
    },

    /**
     * 用途说明：触发启动缩略图生成任务
     * 入参说明：rebuildAll (Boolean) - 是否重构所有缩略图
     * 返回值说明：无
     */
    async handleStartThumbnail(rebuildAll = false) {
        try {
            const response = await RepositoryAPI.startThumbnailGeneration(rebuildAll);
            if (response.status === 'success') {
                Toast.show('缩略图任务已启动');
                this.enterThumbnailGeneratingState();
            } else {
                Toast.show(response.message);
            }
        } catch (error) {
            Toast.show('启动失败');
        }
    },

    /**
     * 用途说明：触发停止缩略图生成任务
     * 入参说明：无
     * 返回值说明：无
     */
    async handleStopThumbnail() {
        UIComponents.showConfirmModal({
            title: '停止确认',
            message: '确定要停止缩略图生成吗？',
            confirmText: '停止',
            onConfirm: async () => {
                try {
                    await RepositoryAPI.stopThumbnailGeneration();
                    Toast.show('正在停止任务...');
                } catch (error) {
                    Toast.show('请求停止失败');
                }
            }
        });
    },

    /**
     * 用途说明：进入缩略图生成监控状态
     * 入参说明：无
     * 返回值说明：无
     */
    enterThumbnailGeneratingState() {
        UIController.toggleThumbnailUI(true);
        if (!State.thumbnailInterval) {
            State.thumbnailInterval = setInterval(() => this.checkThumbnailStatus(), 2000);
        }
    },

    /**
     * 用途说明：检查缩略图生成状态
     * 入参说明：无
     * 返回值说明：无
     */
    async checkThumbnailStatus() {
        try {
            const response = await RepositoryAPI.getThumbnailProgress();
            if (response && response.status === 'success') {
                const { status, progress } = response.data;
                if (status === ProgressStatus.PROCESSING) {
                    if (!State.thumbnailInterval) {
                        this.enterThumbnailGeneratingState();
                    }
                    UIController.updateThumbnailProgress(progress);
                } else {
                    if (State.thumbnailInterval) {
                        clearInterval(State.thumbnailInterval);
                        State.thumbnailInterval = null;
                        Toast.show('缩略图任务已结束');
                        this.loadFileList();
                    }
                    UIController.toggleThumbnailUI(false);
                }
            }
        } catch (error) {
            console.error('获取缩略图进度失败:', error);
        }
    }
};

// 页面加载完成后启动应用
document.addEventListener('DOMContentLoaded', () => App.init());
