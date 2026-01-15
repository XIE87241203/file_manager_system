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
    selectedPaths: new Set(),
    settings: null,
    paginationController: null
};

// --- UI 控制模块 ---
const UIController = {
    elements: {},

    /**
     * 用途说明：初始化 UI 控制器
     */
    init() {
        // 使用公用组件初始化顶部栏
        UIComponents.initRepoHeader({
            searchPlaceholder: '搜索文件名 (正则模糊匹配)...',
            showHistoryCheckbox: true,
            rightBtnText: '建立索引',
            rightBtnId: 'btn-scan',
            onSearch: () => App.handleSearch(),
            onHistoryChange: () => App.handleSearch()
        });

        this.elements = {
            tableBody: document.getElementById('file-list-body'),
            scanBtn: document.getElementById('btn-scan'),
            searchInput: document.getElementById('search-input'),
            searchHistoryCheckbox: document.getElementById('search-history-checkbox'),
            selectAllCheckbox: document.getElementById('select-all-checkbox'),
            deleteSelectedBtn: document.getElementById('btn-delete-selected'),
            thumbnailBtn: document.getElementById('btn-thumbnail'),
            thumbnailProgressText: document.getElementById('thumbnail-progress-text'),
            sortableHeaders: document.querySelectorAll('th.sortable'),
            mainContent: document.getElementById('repo-main-content')
        };

        // 初始化分页组件
        State.paginationController = UIComponents.initPagination('pagination-container', {
            limit: State.limit,
            onPageChange: (newPage) => {
                State.page = newPage;
                App.loadFileList();
                window.scrollTo(0, 0);
            }
        });

        // 绑定表格选择逻辑
        UIComponents.bindTableSelection({
            tableBody: this.elements.tableBody,
            selectAllCheckbox: this.elements.selectAllCheckbox,
            selectedSet: State.selectedPaths,
            onSelectionChange: () => this.updateDeleteButtonVisibility()
        });
    },

    /**
     * 用途说明：渲染文件表格内容
     */
    renderTable(list) {
        const { tableBody, selectAllCheckbox } = this.elements;
        tableBody.innerHTML = '';
        
        if (selectAllCheckbox) {
            selectAllCheckbox.checked = false;
            const checkHeader = document.querySelector('.col-check');
            if (checkHeader) checkHeader.style.display = State.searchHistory ? 'none' : 'table-cell';
        }

        if (!list || list.length === 0) {
            tableBody.innerHTML = UIComponents.getEmptyTableHtml(State.searchHistory ? 4 : 5, '暂无索引文件');
            return;
        }

        list.forEach(file => {
            const isChecked = State.selectedPaths.has(file.file_path);
            const tr = document.createElement('tr');
            tr.setAttribute('data-path', file.file_path);
            if (isChecked) tr.classList.add('selected-row');
            
            const fileName = UIComponents.getFileName(file.file_path);
            let html = `
                <td class="col-name" title="${fileName}">${fileName}</td>
                <td class="col-path" title="${file.file_path}">${file.file_path}</td>
                <td class="col-md5"><code>${file.file_md5}</code></td>
                <td class="col-time">${file.scan_time || file.delete_time}</td>
            `;

            if (!State.searchHistory) {
                html += `
                    <td class="col-check">
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

    updateSortUI(field, order) {
        UIComponents.updateSortUI(this.elements.sortableHeaders, field, order);
    },

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

    updateDeleteButtonVisibility() {
        const { deleteSelectedBtn } = this.elements;
        if (!deleteSelectedBtn) return;
        
        if (State.searchHistory) {
            deleteSelectedBtn.classList.add('hidden');
            return;
        }

        if (State.selectedPaths.size > 0) {
            deleteSelectedBtn.classList.remove('hidden');
            deleteSelectedBtn.textContent = `移入回收站 (${State.selectedPaths.size})`;
        } else {
            deleteSelectedBtn.classList.add('hidden');
        }
    },

    toggleThumbnailUI(isGenerating) {
        const { thumbnailBtn, thumbnailProgressText } = this.elements;
        if (!thumbnailBtn) return;

        if (isGenerating) {
            thumbnailBtn.textContent = '停止生成';
            thumbnailBtn.className = 'btn-text-danger-small';
            thumbnailProgressText.classList.remove('hidden');
        } else {
            thumbnailBtn.textContent = '生成缩略图';
            thumbnailBtn.className = 'btn-secondary-small';
            thumbnailProgressText.classList.add('hidden');
        }
    },

    updateThumbnailProgress(progress) {
        const { thumbnailProgressText } = this.elements;
        if (thumbnailProgressText && progress) {
            thumbnailProgressText.textContent = progress.message || '';
        }
    }
};

// --- API 交互模块 ---
const RepositoryAPI = {
    async getFileList(params) {
        const query = new URLSearchParams(params).toString();
        return await Request.get('/api/file_repository/list?' + query);
    },

    async moveToRecycleBin(filePaths) {
        return await Request.post('/api/file_repository/move_to_recycle_bin', { file_paths: filePaths });
    },

    async startScan(fullScan = false) {
        return await Request.post('/api/file_repository/scan', { full_scan: fullScan });
    },

    async stopScan() {
        return await Request.post('/api/file_repository/stop', {});
    },

    async getProgress() {
        return await Request.get('/api/file_repository/progress');
    },

    async startThumbnailGeneration(rebuildAll = false) {
        return await Request.post('/api/file_repository/thumbnail/start', { rebuild_all: rebuildAll });
    },

    async stopThumbnailGeneration() {
        return await Request.post('/api/file_repository/thumbnail/stop', {});
    },

    async getThumbnailProgress() {
        return await Request.get('/api/file_repository/thumbnail/progress');
    }
};

// --- 应用逻辑主入口 ---
const App = {
    async init() {
        UIController.init();
        this.bindEvents();
        await this.loadSettings();
        this.loadFileList();
        this.checkScanStatus();
        this.checkThumbnailStatus();
    },

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

    bindEvents() {
        const { scanBtn, sortableHeaders, deleteSelectedBtn, thumbnailBtn } = UIController.elements;

        if (scanBtn) {
            scanBtn.onclick = () => {
                if (scanBtn.textContent === '建立索引') this.confirmStartScan();
                else this.handleStopScan();
            };
        }

        if (thumbnailBtn) {
            thumbnailBtn.onclick = () => {
                if (thumbnailBtn.textContent === '生成缩略图') this.confirmStartThumbnail();
                else this.handleStopThumbnail();
            };
        }

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

        if (deleteSelectedBtn) {
            deleteSelectedBtn.onclick = () => this.handleMoveToRecycleBin();
        }
    },

    handleSearch() {
        const { searchInput, searchHistoryCheckbox } = UIController.elements;
        State.search = searchInput.value.trim();
        State.searchHistory = searchHistoryCheckbox.checked;
        State.page = 1;
        State.selectedPaths.clear(); 
        this.loadFileList();
    },

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
            State.paginationController.update(data.total, data.page);
        } else {
            Toast.show(response.message);
        }
    },

    confirmStartScan() {
        UIComponents.showConfirmModal({
            title: '建立索引',
            message: '是否开始建立文件索引？不选中“重新扫描全部索引”将仅扫描新增文件。',
            checkbox: { label: '重新扫描全部索引', checked: false },
            confirmText: '开始扫描',
            onConfirm: (fullScan) => this.handleStartScan(fullScan)
        });
    },

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

    async handleStopScan() {
        const response = await RepositoryAPI.stopScan();
        if (response.status === 'success') {
            Toast.show('已发送停止指令');
        }
    },

    startScanPolling() {
        if (State.scanInterval) clearInterval(State.scanInterval);
        State.scanInterval = setInterval(async () => {
            const response = await RepositoryAPI.getProgress();
            if (response.status === 'success') {
                const data = response.data;
                if (data.status === ProgressStatus.PROCESSING) {
                    UIComponents.renderProgress('.repo-container', data.progress);
                } else {
                    this.stopScanPolling();
                    UIController.toggleScanUI(false);
                    if (data.status === ProgressStatus.COMPLETED) {
                        Toast.show('扫描完成');
                        State.page = 1;
                        this.loadFileList();
                    }
                }
            }
        }, 1000);
    },

    stopScanPolling() {
        if (State.scanInterval) {
            clearInterval(State.scanInterval);
            State.scanInterval = null;
        }
        UIComponents.hideProgressBar('.repo-container');
    },

    async checkScanStatus() {
        const response = await RepositoryAPI.getProgress();
        if (response.status === 'success' && response.data.status === ProgressStatus.PROCESSING) {
            UIController.toggleScanUI(true);
            UIComponents.showProgressBar('.repo-container', '正在扫描...');
            this.startScanPolling();
        }
    },

    async handleMoveToRecycleBin() {
        if (State.selectedPaths.size === 0) return;
        UIComponents.showConfirmModal({
            title: '移入回收站',
            message: `确定要将选中的 ${State.selectedPaths.size} 个文件移入回收站吗？`,
            confirmText: '确定移动',
            onConfirm: async () => {
                const response = await RepositoryAPI.moveToRecycleBin(Array.from(State.selectedPaths));
                if (response.status === 'success') {
                    Toast.show('已移入回收站');
                    State.selectedPaths.clear();
                    this.loadFileList();
                } else {
                    Toast.show(response.message);
                }
            }
        });
    },

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

    async handleStopThumbnail() {
        const response = await RepositoryAPI.stopThumbnailGeneration();
        if (response.status === 'success') {
            Toast.show('已发送停止指令');
        }
    },

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

    stopThumbnailPolling() {
        if (State.thumbnailInterval) {
            clearInterval(State.thumbnailInterval);
            State.thumbnailInterval = null;
        }
    },

    async checkThumbnailStatus() {
        const response = await RepositoryAPI.getThumbnailProgress();
        if (response.status === 'success' && response.data.status === ProgressStatus.PROCESSING) {
            UIController.toggleThumbnailUI(true);
            this.startThumbnailPolling();
        }
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
