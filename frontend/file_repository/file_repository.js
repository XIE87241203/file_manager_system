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
    fileType: '', // 新增：文件类型筛选
    searchHistory: false,
    scanInterval: null,
    thumbnailInterval: null,
    thumbnailCount: 0, // 新增：记录缩略图剩余数量
    selectedPaths: new Set(),
    settings: null
};

// --- UI 控制模块 ---
const UIController = {
    elements: {},

    /**
     * 用途说明：初始化 UI 控制器，绑定页面元素及初始化公用组件
     * 入参说明：无
     * 返回值说明：无
     */
    init() {
        // 使用公用组件初始化顶部栏
        SearchHeaderToolbar.init({
            searchHint: I18nManager.t('file_repo.search_hint'),
            searchCallback: (content) => {
                State.search = content;
                App.handleSearch();
            },
            menuCallback: (e) => this.showMenu(e)
        });

        this.elements = {
            tableBody: document.getElementById('file-list-body'),
            selectAllCheckbox: document.getElementById('select-all-checkbox'),
            deleteSelectedBtn: document.getElementById('btn-delete-selected'),
            sortableHeaders: document.querySelectorAll('th.sortable'),
            filterFileType: document.getElementById('filter-file-type'), // 新增：类型筛选下拉框
            mainContent: document.getElementById('repo-main-content')
        };

        // 绑定表格选择逻辑
        UIComponents.bindTableSelection({
            tableBody: this.elements.tableBody,
            selectAllCheckbox: this.elements.selectAllCheckbox,
            selectedSet: State.selectedPaths,
            idAttribute: 'data-path',
            onSelectionChange: () => this.updateDeleteButtonVisibility()
        });
    },

    /**
     * 用途说明：显示或切换菜单下拉列表的显示状态，并动态处理多语言及悬停文案。
     * 入参说明：event (Event) - 点击事件对象
     * 返回值说明：无
     */
    showMenu(event) {
        const menuBtn = document.getElementById('btn-menu');
        const rect = menuBtn.getBoundingClientRect();

        // 创建或获取菜单容器
        let menu = document.getElementById('repo-action-menu');
        if (!menu) {
            menu = document.createElement('div');
            menu.id = 'repo-action-menu';
            menu.className = 'dropdown-menu';
            document.body.appendChild(menu);

            // 点击外部关闭
            document.addEventListener('click', (e) => {
                if (!menu.contains(e.target) && !menuBtn.contains(e.target)) {
                    menu.classList.remove('show');
                }
            });
        }

        // 如果菜单已经显示，则关闭它（实现再次点击关闭逻辑）
        if (menu.classList.contains('show')) {
            menu.classList.remove('show');
            return;
        }

        const isScanning = App.isScanning();
        const scanBtnText = isScanning ? I18nManager.t('file_repo.menu_stop_scan') : I18nManager.t('file_repo.menu_start_scan');
        const scanBtnClass = isScanning ? 'menu-item text-danger' : 'menu-item';

        const isThumbnailGenerating = State.thumbnailInterval !== null;
        const thumbnailProgressText = I18nManager.t('file_repo.menu_thumb_remaining', { count: State.thumbnailCount });
        const thumbnailStartText = I18nManager.t('file_repo.menu_start_thumb');
        const thumbnailStopText = I18nManager.t('file_repo.menu_stop_thumb');

        const initialThumbnailText = isThumbnailGenerating ? thumbnailProgressText : thumbnailStartText;
        const thumbnailClass = isThumbnailGenerating ? 'menu-item thumbnail-btn-generating' : 'menu-item';

        // 渲染菜单内容
        menu.innerHTML = `
            <div class="${scanBtnClass}" id="menu-btn-scan">${scanBtnText}</div>
            <div class="${thumbnailClass}" id="menu-btn-thumbnail"><span>${initialThumbnailText}</span></div>
            <div class="menu-divider"></div>
            <label class="menu-item checkbox-item">
                <span>${I18nManager.t('file_repo.menu_search_history')}</span>
                <input type="checkbox" id="menu-search-history" ${State.searchHistory ? 'checked' : ''}>
            </label>
        `;

        const thumbBtn = menu.querySelector('#menu-btn-thumbnail');
        const thumbSpan = thumbBtn.querySelector('span');

        // 动态处理缩略图按钮的悬停文案（替代 CSS ::after）
        if (isThumbnailGenerating) {
            thumbBtn.onmouseenter = () => { thumbSpan.innerText = thumbnailStopText; };
            thumbBtn.onmouseleave = () => { thumbSpan.innerText = I18nManager.t('file_repo.menu_thumb_remaining', { count: State.thumbnailCount }); };
        }

        // 绑定菜单项事件
        menu.querySelector('#menu-btn-scan').onclick = () => {
            menu.classList.remove('show');
            if (isScanning) App.handleStopScan();
            else App.confirmStartScan();
        };

        thumbBtn.onclick = () => {
            menu.classList.remove('show');
            if (isThumbnailGenerating) App.handleStopThumbnail();
            else App.confirmStartThumbnail();
        };

        const historyCheck = menu.querySelector('#menu-search-history');
        historyCheck.onchange = () => {
            State.searchHistory = historyCheck.checked;
            App.handleSearch();
        };

        // 定位并显示
        menu.style.top = `${rect.bottom + 5}px`;
        menu.style.left = `${rect.right - 160}px`;
        menu.classList.add('show');
    },

    /**
     * 用途说明：渲染文件表格内容
     * 入参说明：list (Array) - 文件数据列表
     * 返回值说明：无
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
            tableBody.innerHTML = UIComponents.getEmptyTableHtml(State.searchHistory ? 7 : 8, I18nManager.t('file_repo.empty_hint'));
            return;
        }

        list.forEach(file => {
            const isChecked = State.selectedPaths.has(file.file_path);
            const tr = document.createElement('tr');
            tr.setAttribute('data-path', file.file_path);
            if (isChecked) tr.classList.add('selected-row');
            
            const fileName = file.file_name || I18nManager.t('file_repo.unknown_file');
            const fileSizeStr = CommonUtils.formatFileSize(file.file_size);
            const durationStr = file.file_type === 'video' ? CommonUtils.formatDuration(file.video_duration) : '-';

            const isVideo = file.file_type === 'video';
            const playBtnHtml = isVideo ? `<span class="play-btn" title="${I18nManager.t('file_repo.play_video')}"><i class="play-icon">▶</i></span>` : '';

            let html = `
                <td class="col-name" title="${fileName}">${playBtnHtml}${fileName}</td>
                <td class="col-size">${fileSizeStr}</td>
                <td class="col-path" title="${file.file_path}">${file.file_path}</td>
                <td class="col-type">${file.file_type || I18nManager.t('file_repo.unknown')}</td>
                <td class="col-duration">${durationStr}</td>
                <td class="col-codec">${file.video_codec || 'N/A'}</td>
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
            
            if (isVideo) {
                const playBtn = tr.querySelector('.play-btn');
                playBtn.onclick = (e) => {
                    e.stopPropagation();
                    App.handlePlayVideo(file.file_path);
                };
            }

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
     * 用途说明：更新表头排序 UI 状态
     * 入参说明：field (string) - 排序字段；order (string) - 排序方向
     * 返回值说明：无
     */
    updateSortUI(field, order) {
        UIComponents.updateSortUI(this.elements.sortableHeaders, field, order);
    },

    /**
     * 用途说明：切换扫描时的 UI 遮罩
     * 入参说明：isScanning (boolean) - 是否正在扫描
     * 返回值说明：无
     */
    toggleScanUI(isScanning) {
        const { mainContent } = this.elements;
        if (isScanning) {
            mainContent.style.visibility = 'hidden';
        } else {
            mainContent.style.visibility = 'visible';
        }
    },

    /**
     * 用途说明：根据选中情况更新批量删除按钮的可见性及文字
     * 入参说明：无
     * 返回值说明：无
     */
    updateDeleteButtonVisibility() {
        const { deleteSelectedBtn } = this.elements;
        if (!deleteSelectedBtn) return;
        
        if (State.searchHistory) {
            deleteSelectedBtn.classList.add('hidden');
            return;
        }

        if (State.selectedPaths.size > 0) {
            deleteSelectedBtn.classList.remove('hidden');
            deleteSelectedBtn.setAttribute('title', I18nManager.t('common.delete_selected_count', { count: State.selectedPaths.size }));
        } else {
            deleteSelectedBtn.classList.add('hidden');
        }
    },

    /**
     * 用途说明：切换缩略图生成相关的 UI 状态
     * 入参说明：isGenerating (boolean) - 是否正在生成
     * 返回值说明：无
     */
    toggleThumbnailUI(isGenerating) {
        const menuThumbnailBtn = document.getElementById('menu-btn-thumbnail');
        if (menuThumbnailBtn) {
            if (isGenerating) {
                menuThumbnailBtn.className = 'menu-item thumbnail-btn-generating';
                menuThumbnailBtn.innerHTML = `<span>${I18nManager.t('file_repo.menu_thumb_remaining', { count: State.thumbnailCount })}</span>`;
            } else {
                menuThumbnailBtn.className = 'menu-item';
                menuThumbnailBtn.innerHTML = `<span>${I18nManager.t('file_repo.menu_start_thumb')}</span>`;
            }
        }
    },

    /**
     * 用途说明：更新缩略图生成进度文字
     * 入参说明：count (number) - 队列剩余数量
     * 返回值说明：无
     */
    updateThumbnailProgress(count) {
        State.thumbnailCount = count;
        const menuThumbnailBtn = document.getElementById('menu-btn-thumbnail');
        if (menuThumbnailBtn && State.thumbnailInterval !== null) {
            const span = menuThumbnailBtn.querySelector('span');
            if (span) {
                // 如果鼠标当前不在按钮上，则更新进度文字；否则保留“停止”文案
                if (!menuThumbnailBtn.matches(':hover')) {
                    span.textContent = count > 0 ? I18nManager.t('file_repo.menu_thumb_remaining', { count: count }) : I18nManager.t('common.processing');
                }
            }
        }
    }
};

// --- 应用逻辑主入口 ---
const App = {
    /**
     * 用途说明：应用初始化，启动各模块状态检查
     * 入参说明：无
     * 返回值说明：无
     */
    init() {
        // 初始化多语言
        I18nManager.init();
        I18nManager.render();

        UIController.init();
        this.bindEvents();
        this.loadSettings();
        this.loadFileList();
        this.checkScanStatus();
        this.checkThumbnailStatus();
    },

    /**
     * 用途说明：判断当前是否处于扫描中状态
     * 返回值说明：boolean - 是否扫描中
     */
    isScanning() {
        return State.scanInterval !== null;
    },

    /**
     * 用途说明：异步加载系统设置
     * 入参说明：无
     * 返回值说明：无
     */
    loadSettings() {
        FileRepositoryAPI.getSettings(
            (data) => { State.settings = data; },
            (msg) => console.error(I18nManager.t('file_repo.load_settings_failed'), msg)
        );
    },

    /**
     * 用途说明：绑定页面交互事件（排序、删除、缩略图生成、类型筛选等）
     * 入参说明：无
     * 返回值说明：无
     */
    bindEvents() {
        const { sortableHeaders, deleteSelectedBtn, filterFileType } = UIController.elements;

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

        if (filterFileType) {
            filterFileType.onchange = () => {
                State.fileType = filterFileType.value;
                State.page = 1;
                this.loadFileList();
            };
        }
    },

    /**
     * 用途说明：处理搜索触发逻辑，重置分页并刷新列表
     * 入参说明：无
     * 返回值说明：无
     */
    handleSearch() {
        State.page = 1;
        // 修正逻辑
        State.selectedPaths.clear();
        this.loadFileList();
    },

    /**
     * 用途说明：调用接口加载文件列表数据
     * 入参说明：无
     * 返回值说明：无
     */
    loadFileList() {
        const params = {
            page: State.page,
            limit: State.limit,
            sort_by: State.sortBy,
            order_asc: State.order === 'ASC',
            search: State.search,
            file_type: State.fileType,
            search_history: State.searchHistory
        };

        FileRepositoryAPI.getFileList(params,
            (data) => {
                UIController.renderTable(data.list);

                // 使用公共 PageBar 组件渲染分页栏
                PageBar.init({
                    containerId: 'pagination-container',
                    totalItems: data.total,
                    pageSize: State.limit,
                    currentPage: data.page,
                    onPageChange: (newPage) => {
                        State.page = newPage;
                        this.loadFileList();
                        window.scrollTo(0, 0);
                    }
                });
            },
            (msg) => Toast.show(msg)
        );
    },

    /**
     * 用途说明：处理视频播放请求，跳转到专用播放页面
     * @param {string} filePath - 入参说明：视频文件路径
     * @returns {void} - 返回值说明：无
     */
    handlePlayVideo(filePath) {
        const playPageUrl = `../video_player/video_player.html?path=${encodeURIComponent(filePath)}`;
        window.location.href = playPageUrl;
    },

    /**
     * 用途说明：弹出确认框询问是否开始建立索引
     * 入参说明：无
     * 返回值说明：无
     */
    confirmStartScan() {
        UIComponents.showConfirmModal({
            title: I18nManager.t('file_repo.scan_confirm_title'),
            message: I18nManager.t('file_repo.scan_confirm_msg'),
            checkbox: { label: I18nManager.t('file_repo.scan_rebuild_label'), checked: false },
            confirmText: I18nManager.t('file_repo.menu_start_scan'),
            onConfirm: (fullScan) => this.handleStartScan(fullScan)
        });
    },

    /**
     * 用途说明：调用接口正式启动扫描任务
     * @param {boolean} fullScan - 入参说明：是否进行全量扫描
     * @returns {void} - 返回值说明：无
     */
    handleStartScan(fullScan = false) {
        FileRepositoryAPI.startScan(fullScan,
            () => {
                Toast.show(I18nManager.t('file_repo.scan_started'));
                UIController.toggleScanUI(true);
                UIComponents.showProgressBar('.main-content', I18nManager.t('file_repo.scanning'));
                this.startScanPolling();
            },
            (msg) => Toast.show(msg)
        );
    },

    /**
     * 用途说明：调用接口停止正在进行的扫描任务
     * 入参说明：无
     * 返回值说明：无
     */
    handleStopScan() {
        FileRepositoryAPI.stopScan(
            () => Toast.show(I18nManager.t('file_repo.stop_cmd_sent')),
            (msg) => Toast.show(msg)
        );
    },

    /**
     * 用途说明：启动扫描进度的实时轮询
     * 入参说明：无
     * 返回值说明：无
     */
    startScanPolling() {
        if (State.scanInterval) clearInterval(State.scanInterval);
        State.scanInterval = setInterval(() => {
            FileRepositoryAPI.getProgress(
                (data) => {
                    if (data.status === ProgressStatus.PROCESSING) {
                        UIComponents.renderProgress('.main-content', data.progress);
                    } else {
                        this.stopScanPolling();
                        UIController.toggleScanUI(false);
                        if (data.status === ProgressStatus.COMPLETED) {
                            Toast.show(I18nManager.t('file_repo.scan_finished'));
                            State.page = 1;
                            this.loadFileList();
                        }
                    }
                },
                (msg) => {
                    this.stopScanPolling();
                    UIController.toggleScanUI(false);
                    Toast.show(msg);
                }
            );
        }, 1000);
    },

    /**
     * 用途说明：停止扫描进度的轮询任务
     * 入参说明：无
     * 返回值说明：无
     */
    stopScanPolling() {
        if (State.scanInterval) {
            clearInterval(State.scanInterval);
            State.scanInterval = null;
        }
        UIComponents.hideProgressBar('.main-content');
    },

    /**
     * 用途说明：页面初始化时检查是否有正在运行的扫描任务
     * 入参说明：无
     * 返回值说明：无
     */
    checkScanStatus() {
        FileRepositoryAPI.getProgress(
            (data) => {
                if (data.status === ProgressStatus.PROCESSING) {
                    UIController.toggleScanUI(true);
                    UIComponents.showProgressBar('.main-content', I18nManager.t('file_repo.scanning'));
                    this.startScanPolling();
                }
            },
            () => {}
        );
    },

    /**
     * 用途说明：处理将选中的文件移入回收站
     * 入参说明：无
     * 返回值说明：无
     */
    handleMoveToRecycleBin() {
        if (State.selectedPaths.size === 0) return;
        UIComponents.showConfirmModal({
            title: I18nManager.t('recycle_bin.delete_confirm_title'),
            message: I18nManager.t('file_repo.move_to_recycle_confirm', { count: State.selectedPaths.size }),
            confirmText: I18nManager.t('common.confirm'),
            onConfirm: () => {
                FileRepositoryAPI.moveToRecycleBin(Array.from(State.selectedPaths),
                    () => {
                        Toast.show(I18nManager.t('common.success'));
                        State.selectedPaths.clear();
                        this.loadFileList();
                    },
                    (msg) => Toast.show(msg)
                );
            }
        });
    },

    /**
     * 用途说明：弹出确认框开始缩略图生成
     * 入参说明：无
     * 返回值说明：无
     */
    confirmStartThumbnail() {
        UIComponents.showConfirmModal({
            title: I18nManager.t('file_repo.thumb_confirm_title'),
            message: I18nManager.t('file_repo.thumb_confirm_msg'),
            checkbox: { label: I18nManager.t('file_repo.thumb_rebuild_label'), checked: false },
            confirmText: I18nManager.t('common.confirm'),
            onConfirm: (rebuildAll) => {
                FileRepositoryAPI.startThumbnailGeneration(rebuildAll,
                    () => {
                        Toast.show(I18nManager.t('file_repo.thumb_started'));
                        UIController.toggleThumbnailUI(true);
                        this.startThumbnailPolling();
                    },
                    (msg) => Toast.show(msg)
                );
            }
        });
    },

    /**
     * 用途说明：调用接口停止缩略图生成
     * 入参说明：无
     * 返回值说明：无
     */
    handleStopThumbnail() {
        FileRepositoryAPI.stopThumbnailGeneration(
            () => Toast.show(I18nManager.t('file_repo.stop_cmd_sent')),
            (msg) => Toast.show(msg)
        );
    },

    /**
     * 用途说明：启动缩略图进度轮询
     * 入参说明：无
     * 返回值说明：无
     */
    startThumbnailPolling() {
        if (State.thumbnailInterval) clearInterval(State.thumbnailInterval);
        State.thumbnailInterval = setInterval(() => {
            FileRepositoryAPI.getThumbnailQueueCount(
                (count) => {
                    State.thumbnailCount = count;
                    if (count > 0) {
                        UIController.updateThumbnailProgress(count);
                    } else {
                        this.stopThumbnailPolling();
                        UIController.toggleThumbnailUI(false);
                        Toast.show(I18nManager.t('file_repo.thumb_finished'));
                        this.loadFileList();
                    }
                },
                () => {
                    this.stopThumbnailPolling();
                    UIController.toggleThumbnailUI(false);
                }
            );
        }, 1500);
    },

    /**
     * 用途说明：停止缩略图轮询任务
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
     * 用途说明：初始化检查缩略图生成状态
     * 入参说明：无
     * 返回值说明：无
     */
    checkThumbnailStatus() {
        FileRepositoryAPI.getThumbnailQueueCount(
            (count) => {
                State.thumbnailCount = count;
                if (count > 0) {
                    UIController.toggleThumbnailUI(true);
                    this.startThumbnailPolling();
                }
            },
            () => {}
        );
    }
};

// 启动应用
document.addEventListener('DOMContentLoaded', () => App.init());
