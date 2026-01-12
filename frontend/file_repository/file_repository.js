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
    settings: null, // 存储系统设置
    paginationController: null // 分页控制器实例
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
        // 初始化公用分页组件
        State.paginationController = UIComponents.initPagination('pagination-container', {
            limit: State.limit,
            onPageChange: (newPage) => {
                State.page = newPage;
                App.loadFileList();
                window.scrollTo(0, 0);
            }
        });
        // 动态避开头部高度
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
        
        if (selectAllCheckbox) {
            selectAllCheckbox.checked = false;
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
            
            // 列表的文件名改为通过截取路径获得
            const fileName = UIComponents.getFileName(file.file_path);
            
            let html = `
                <td title="${fileName}">${fileName}</td>
                <td title="${file.file_path}">${file.file_path}</td>
                <td><code>${file.file_md5}</code></td>
                <td>${file.scan_time}</td>
            `;

            if (!State.searchHistory) {
                html += `
                    <td style="text-align: center;">
                        <input type="checkbox" class="file-checkbox" data-path="${file.file_path}" ${isChecked ? 'checked' : ''}>
                    </td>
                `;
            }

            tr.innerHTML = html;
            
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
     * 用途说明：更新分页控件显示状态（调用公共组件）
     * 入参说明：total (Number) - 总记录数，page (Number) - 当前页码
     * 返回值说明：无
     */
    updatePagination(total, page) {
        if (State.paginationController) {
            State.paginationController.update(total, page);
        }
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
     * 入参说明：params (Object) - 查询参数
     * 返回值说明：Promise - 请求响应结果
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
     * 入参说明：fullScan (Boolean) - 是否全量扫描
     * 返回值说明：Promise - 请求响应结果
     */
    async startScan(fullScan = false) {
        return await Request.post('/api/file_repository/scan', { full_scan: fullScan }, {}, true);
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
            scanBtn, searchInput, searchBtn, 
            searchHistoryCheckbox, duplicateBtn, sortableHeaders,
            selectAllCheckbox, tableBody, deleteSelectedBtn, thumbnailBtn,
            backBtn
        } = UIController.elements;


        if (backBtn) {
            backBtn.onclick = () => {
                window.history.back();
            }
        }

        // 搜索逻辑
        const onSearch = () => {
            State.search = searchInput.value.trim();
            State.searchHistory = searchHistoryCheckbox.checked;
            State.page = 1;
            State.selectedPaths.clear(); 
            this.loadFileList();
        };
        if (searchBtn) searchBtn.onclick = onSearch;
        if (searchInput) searchInput.onkeypress = (e) => { if (e.key === 'Enter') onSearch(); };
        if (searchHistoryCheckbox) searchHistoryCheckbox.onchange = onSearch;

        // 索引任务逻辑
        if (scanBtn) {
            scanBtn.onclick = () => {
                if (scanBtn.textContent === '建立索引') this.confirmStartScan();
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

        // 跳转查重
        if (duplicateBtn) {
            duplicateBtn.onclick = () => {
                window.location.href = 'duplicate_check/duplicate_check.html';
            };
        }

        // 排序逻辑
        sortableHeaders.forEach(th => {
            th.onclick = () => {
                const field = th.getAttribute('data-field');
                if (State.sortBy === field) {
                    State.order = State.order === 'ASC' ? 'DESC' : 'ASC';
                } else {
                    State.sortBy = field;
                    State.order = 'DESC';
                }
                UIController.updateSortUI(State.sortBy, State.order);
                this.loadFileList();
            };
        });

        // 全选/取消全选
        if (selectAllCheckbox) {
            selectAllCheckbox.onchange = (e) => {
                const checkboxes = tableBody.querySelectorAll('.file-checkbox');
                checkboxes.forEach(cb => {
                    cb.checked = e.target.checked;
                    const path = cb.getAttribute('data-path');
                    const tr = cb.closest('tr');
                    if (e.target.checked) {
                        State.selectedPaths.add(path);
                        tr.classList.add('selected-row');
                    } else {
                        State.selectedPaths.delete(path);
                        tr.classList.remove('selected-row');
                    }
                });
                UIController.updateDeleteButtonVisibility();
            };
        }

        // 行点击/复选框点击
        tableBody.onclick = (e) => {
            const tr = e.target.closest('tr');
            if (!tr) return;
            const path = tr.getAttribute('data-path');
            const checkbox = tr.querySelector('.file-checkbox');
            if (!checkbox) return;

            if (e.target === checkbox) {
                if (checkbox.checked) {
                    State.selectedPaths.add(path);
                    tr.classList.add('selected-row');
                } else {
                    State.selectedPaths.delete(path);
                    tr.classList.remove('selected-row');
                    if (selectAllCheckbox) selectAllCheckbox.checked = false;
                }
            } else {
                checkbox.checked = !checkbox.checked;
                if (checkbox.checked) {
                    State.selectedPaths.add(path);
                    tr.classList.add('selected-row');
                } else {
                    State.selectedPaths.delete(path);
                    tr.classList.remove('selected-row');
                    if (selectAllCheckbox) selectAllCheckbox.checked = false;
                }
            }
            UIController.updateDeleteButtonVisibility();
        };

        // 批量删除
        if (deleteSelectedBtn) {
            deleteSelectedBtn.onclick = () => this.handleDeleteSelected();
        }
    },

    /**
     * 用途说明：加载文件列表数据
     * 入参说明：无
     * 返回值说明：无
     */
    async loadFileList() {
        const params = {
            page: State.page,
            limit: State.limit,
            sort_by: State.sortBy,
            order_asc: State.order === 'ASC',
            search: State.search,
            search_history: State.searchHistory
        };

        const response = await RepositoryAPI.getFileList(params);
        if (response.status === 'success') {
            const data = response.data;
            UIController.renderTable(data.list);
            UIController.updatePagination(data.total, data.page);
        } else {
            Toast.show(response.message);
        }
    },

    /**
     * 用途说明：弹出二次确认并启动扫描
     * 入参说明：无
     * 返回值说明：无
     */
    confirmStartScan() {
        UIComponents.showConfirmModal({
            title: '建立索引',
            message: '是否开始建立文件索引？不选中“重新扫描全部索引”将仅扫描新增文件。',
            checkbox: { label: '重新扫描全部索引', checked: false },
            confirmText: '开始扫描',
            onConfirm: (fullScan) => {
                this.handleStartScan(fullScan);
            }
        });
    },

    /**
     * 用途说明：实际执行启动扫描
     * 入参说明：fullScan (Boolean) - 是否全量扫描
     * 返回值说明：无
     */
    async handleStartScan(fullScan = false) {
        const response = await RepositoryAPI.startScan(fullScan);
        if (response.status === 'success') {
            Toast.show('扫描任务已启动');
            UIController.toggleScanUI(true);
            UIComponents.showProgressBar('.repo-container', '开始扫描...');
            this.startScanPolling();
        } else {
            Toast.show(response.message);
        }
    },

    /**
     * 用途说明：处理停止扫描
     * 入参说明：无
     * 返回值说明：无
     */
    async handleStopScan() {
        const response = await RepositoryAPI.stopScan();
        if (response.status === 'success') {
            Toast.show('已发送停止指令');
        } else {
            Toast.show(response.message);
        }
    },

    /**
     * 用途说明：轮询扫描状态
     * 入参说明：无
     * 返回值说明：无
     */
    startScanPolling() {
        if (State.scanInterval) clearInterval(State.scanInterval);
        State.scanInterval = setInterval(async () => {
            const response = await RepositoryAPI.getProgress();
            if (response.status === 'success') {
                const data = response.data;
                if (data.status === ProgressStatus.PROCESSING) {
                    UIController.updateProgress(data.progress);
                } else {
                    this.stopScanPolling();
                    UIController.toggleScanUI(false);
                    if (data.status === ProgressStatus.COMPLETED) {
                        Toast.show('扫描完成');
                        State.page = 1;
                        this.loadFileList();
                    } else if (data.status === ProgressStatus.ERROR) {
                        Toast.show('扫描出错: ' + (data.progress.message || '未知错误'));
                    }
                }
            }
        }, 1000);
    },

    /**
     * 用途说明：停止轮询扫描
     * 入参说明：无
     * 返回值说明：无
     */
    stopScanPolling() {
        if (State.scanInterval) {
            clearInterval(State.scanInterval);
            State.scanInterval = null;
        }
        UIComponents.hideProgressBar('.repo-container');
    },

    /**
     * 用途说明：初始检查扫描状态
     * 入参说明：无
     * 返回值说明：无
     */
    async checkScanStatus() {
        const response = await RepositoryAPI.getProgress();
        if (response.status === 'success' && response.data.status === ProgressStatus.PROCESSING) {
            UIController.toggleScanUI(true);
            UIComponents.showProgressBar('.repo-container', '正在扫描...');
            this.startScanPolling();
        }
    },

    /**
     * 用途说明：处理批量删除
     * 入参说明：无
     * 返回值说明：无
     */
    async handleDeleteSelected() {
        if (State.selectedPaths.size === 0) return;
        
        UIComponents.showConfirmModal({
            title: '批量删除',
            message: `确定要物理删除选中的 ${State.selectedPaths.size} 个文件吗？此操作不可撤销！`,
            confirmText: '立即删除',
            onConfirm: async () => {
                const response = await RepositoryAPI.deleteFiles(Array.from(State.selectedPaths));
                if (response.status === 'success') {
                    Toast.show('删除成功');
                    State.selectedPaths.clear();
                    this.loadFileList();
                } else {
                    Toast.show(response.message);
                }
            }
        });
    },

    /**
     * 用途说明：确认并启动缩略图生成
     * 入参说明：无
     * 返回值说明：无
     */
    confirmStartThumbnail() {
        UIComponents.showConfirmModal({
            title: '生成缩略图',
            message: '是否开始生成缩略图？',
            checkbox: { label: '重构所有缩略图', checked: false },
            confirmText: '开始生成',
            onConfirm: async (rebuildAll) => {
                const response = await RepositoryAPI.startThumbnailGeneration(rebuildAll);
                if (response.status === 'success') {
                    Toast.show('任务已启动');
                    UIController.toggleThumbnailUI(true);
                    this.startThumbnailPolling();
                } else {
                    Toast.show(response.message);
                }
            }
        });
    },

    /**
     * 用途说明：处理停止缩略图生成
     * 入参说明：无
     * 返回值说明：无
     */
    async handleStopThumbnail() {
        const response = await RepositoryAPI.stopThumbnailGeneration();
        if (response.status === 'success') {
            Toast.show('已发送停止指令');
        }
    },

    /**
     * 用途说明：轮询缩略图生成状态
     * 入参说明：无
     * 返回值说明：无
     */
    startThumbnailPolling() {
        if (State.thumbnailInterval) clearInterval(State.thumbnailInterval);
        State.thumbnailInterval = setInterval(async () => {
            const response = await RepositoryAPI.getThumbnailProgress();
            if (response.status === 'success') {
                const data = response.data;
                if (data.status === ProgressStatus.PROCESSING) {
                    UIController.updateThumbnailProgress(data.progress);
                } else {
                    this.stopThumbnailPolling();
                    UIController.toggleThumbnailUI(false);
                    if (data.status === ProgressStatus.COMPLETED) {
                        Toast.show('缩略图生成完成');
                        this.loadFileList();
                    }
                }
            }
        }, 1500);
    },

    /**
     * 用途说明：停止轮询缩略图
     * 入参说明：无
     * 返回值说明：无
     */
    stopThumbnailPolling() {
        if (State.thumbnailInterval) {
            clearInterval(State.thumbnailInterval);
            State.thumbnailInterval = null;
        }
    },

    /**
     * 用途说明：初始检查缩略图生成状态
     * 入参说明：无
     * 返回值说明：无
     */
    async checkThumbnailStatus() {
        const response = await RepositoryAPI.getThumbnailProgress();
        if (response.status === 'success' && response.data.status === ProgressStatus.PROCESSING) {
            UIController.toggleThumbnailUI(true);
            this.startThumbnailPolling();
        }
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
