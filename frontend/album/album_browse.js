/**
 * 用途说明：相册浏览页面逻辑，负责按时间/文件名/文件大小全局排序与瀑布流渲染、动态时间轴/字母尺导航、搜索、
 * 无限滚动、按需生成缩略图、单项/批量下载与删除（移入回收站），以及媒体预览弹窗（图片/视频切换、下载、删除）。
 * 模块划分：State（状态）、UIController（DOM 与渲染）、API（接口封装）、App（入口与事件绑定）。
 */

// --- 状态管理 ---
const State = {
    page: 1,
    limit: 30,
    search: '',
    fileType: '', // 媒体类型筛选：'' 全部 / 'image' 仅图片 / 'video' 仅视频
    sidebarVisible: true, // 标尺侧边栏是否由用户手动展开；文件大小排序时自动隐藏
    sortBy: 'album_time', // album_time 时间倒序 / file_name 文件名升序 / file_size 文件大小倒序
    orderAsc: false,
    items: [],
    total: 0,
    loading: false,
    hasMore: true,
    selected: new Set(), // 已选中的文件路径集合
    cardMap: new Map(), // file_path -> { card, item, img, placeholder, placeholderText, groupKey }
    groupMap: new Map(), // 当前排序分组键 -> { key, section, grid, count }
    groupKeys: [], // 分组键列表，严格保持数据库全局排序顺序
    timelineTicks: [], // 动态标尺刻度缓存：[{ el, level, key, year, month }]
    activeGroupKey: '', // 当前滚动位置对应的分组键
    ensureRequested: new Set(), // 已发起缩略图生成请求的路径
    ensureQueue: [], // 缩略图生成待处理队列
    ensureActive: 0, // 当前进行中的缩略图请求数
    ensureMax: 3, // 缩略图请求最大并发数
    previewIndex: -1, // 当前预览索引，-1 表示未打开
    detailWidth: 0, // 详情侧边栏当前宽度（像素），0 表示使用默认宽度
    detailResizing: false, // 是否正在拖动侧边栏边缘
    detailDragStartX: 0, // 拖动开始时的鼠标横坐标
    detailDragStartWidth: 0, // 拖动开始时的侧边栏宽度
    queryToken: 0, // 请求代次，用于丢弃搜索切换后的过期响应
    scanInterval: null, // 索引扫描或缺失信息补全的进度轮询定时器，null 表示当前未运行
    scanTaskType: '', // 当前任务类型：scan 表示建立索引，metadata 表示补全缺少信息
    repoPermission: '', // 当前仓库权限：admin/member，成员仅可浏览
    sentinelObserver: null,
    cardObserver: null
};

// --- API 封装 ---
const API = {
    /**
     * 用途说明：获取当前用户在当前仓库中的权限。
     * 入参说明：onSuccess (Function) - 成功回调；onError (Function) - 失败回调。
     * 返回值说明：无
     */
    getCurrentUser(onSuccess, onError) {
        AlbumBrowseRequest.getCurrentUser(onSuccess, onError);
    },

    /**
     * 用途说明：拉取一页相册数据。
     * 入参说明：page (number) - 页码；onSuccess (Function) - 成功回调；onError (Function) - 失败回调。
     * 返回值说明：无
     */
    fetchList(page, onSuccess, onError) {
        AlbumBrowseRequest.list({
            page: page,
            limit: State.limit,
            search: State.search,
            file_type: State.fileType,
            sort_by: State.sortBy,
            order_asc: State.orderAsc
        }, onSuccess, onError);
    },

    /**
     * 用途说明：请求生成单个媒体缩略图。
     * 入参说明：filePath (string) - 媒体路径；onSuccess (Function) - 成功回调；onError (Function) - 失败回调。
     * 返回值说明：无
     */
    ensureThumbnail(filePath, onSuccess, onError) {
        AlbumBrowseRequest.ensureThumbnail(filePath, onSuccess, onError);
    },

    /**
     * 用途说明：将文件移入回收站。
     * 入参说明：filePaths (Array<string>) - 文件路径列表；onSuccess (Function) - 成功回调；onError (Function) - 失败回调。
     * 返回值说明：无
     */
    deleteFiles(filePaths, onSuccess, onError) {
        AlbumBrowseRequest.moveToRecycleBin(filePaths, onSuccess, onError);
    },

    /**
     * 用途说明：启动索引扫描任务。
     * 入参说明：fullScan (boolean) - 是否全量扫描；onSuccess (Function) - 成功回调；onError (Function) - 失败回调。
     * 返回值说明：无
     */
    startScan(fullScan, onSuccess, onError) {
        AlbumBrowseRequest.startScan(fullScan, onSuccess, onError);
    },

    /**
     * 用途说明：启动缺失媒体信息补全任务。
     * 入参说明：onSuccess (Function) - 成功回调；onError (Function) - 失败回调。
     * 返回值说明：无
     */
    refreshMetadata(onSuccess, onError) {
        AlbumBrowseRequest.refreshMetadata(onSuccess, onError);
    },

    /**
     * 用途说明：停止索引扫描任务。
     * 入参说明：onSuccess (Function) - 成功回调；onError (Function) - 失败回调。
     * 返回值说明：无
     */
    stopScan(onSuccess, onError) {
        AlbumBrowseRequest.stopScan(onSuccess, onError);
    },

    /**
     * 用途说明：获取索引扫描进度。
     * 入参说明：onSuccess (Function) - 成功回调；onError (Function) - 失败回调。
     * 返回值说明：无
     */
    getScanProgress(onSuccess, onError) {
        AlbumBrowseRequest.getProgress(onSuccess, onError);
    }
};

// --- UI 控制模块 ---
const UIController = {
    elements: {},

    /**
     * 用途说明：初始化页面 UI、顶部工具栏、滚动监听与预览事件。
     * 入参说明：无
     * 返回值说明：无
     */
    init() {
        I18nManager.init();
        I18nManager.render();

        SearchHeaderToolbar.init({
            searchHint: I18nManager.t('album.search_placeholder'),
            searchCallback: (content) => App.handleSearch(content),
            menuCallback: (e) => this.showMenu(e)
        });

        this.elements = {
            pageContent: document.getElementById('album-page-content'),
            timelineTicks: document.getElementById('album-timeline-ticks'),
            layout: document.getElementById('album-layout'),
            timeline: document.getElementById('album-timeline'),
            sidebarToggle: document.getElementById('album-sidebar-toggle'),
            axis: document.getElementById('album-axis'),
            axisTitle: document.getElementById('album-axis-title'),
            sortFilter: document.getElementById('album-sort-filter'),
            typeFilter: document.getElementById('album-type-filter'),
            waterfall: document.getElementById('album-waterfall'),
            empty: document.getElementById('album-empty'),
            sentinel: document.getElementById('album-sentinel'),
            endTip: document.getElementById('album-end-tip'),
            selectionBar: document.getElementById('album-selection-bar'),
            selectedCount: document.getElementById('album-selected-count'),
            downloadSelectedBtn: document.getElementById('btn-download-selected'),
            deleteSelectedBtn: document.getElementById('btn-delete-selected'),
            cancelSelectionBtn: document.getElementById('btn-cancel-selection'),
            previewMask: document.getElementById('album-preview-mask'),
            previewBody: document.getElementById('album-preview-body'),
            previewName: document.getElementById('album-preview-name'),
            previewSelectBtn: document.getElementById('album-preview-select'),
            previewSelectedCount: document.getElementById('album-preview-selected-count'),
            previewDownloadBtn: document.getElementById('album-preview-download'),
            previewDeleteBtn: document.getElementById('album-preview-delete'),
            previewDetailBtn: document.getElementById('album-preview-detail'),
            previewCloseBtn: document.getElementById('album-preview-close'),
            detailPanel: document.getElementById('album-detail-panel'),
            detailResize: document.getElementById('album-detail-resize'),
            detailCloseBtn: document.getElementById('album-detail-close'),
            detailName: document.getElementById('album-detail-name'),
            detailPath: document.getElementById('album-detail-path'),
            detailCaptureTime: document.getElementById('album-detail-capture-time'),
            detailMtime: document.getElementById('album-detail-mtime'),
            detailSize: document.getElementById('album-detail-size'),
            detailLocation: document.getElementById('album-detail-location'),
            previewPrevBtn: document.getElementById('album-preview-prev'),
            previewNextBtn: document.getElementById('album-preview-next')
        };

        this.initObservers();
        this.bindPreviewEvents();
        this.bindDetailResize();
        this.bindTypeFilter();
        this.bindSortFilter();
        this.bindSidebarToggle();
        this.updateAxisMode();
        this.applyPermissionUI();
    },

    /**
     * 用途说明：按当前仓库权限显示或隐藏删除与索引管理入口，仓库成员仅保留浏览、选择和下载能力。
     * 入参说明：无
     * 返回值说明：无
     */
    applyPermissionUI() {
        const canManage = State.repoPermission === 'admin';
        if (this.elements.deleteSelectedBtn) this.elements.deleteSelectedBtn.classList.toggle('hidden', !canManage);
        if (this.elements.previewDeleteBtn) this.elements.previewDeleteBtn.classList.toggle('hidden', !canManage);
        const menuBtn = document.getElementById('btn-menu');
        if (menuBtn) menuBtn.classList.toggle('hidden', !canManage);
        this.updateSelectionBar();
    },

    /**
     * 用途说明：显示或切换右上角动作菜单，菜单中提供“建立索引/停止索引”入口。
     * 入参说明：event (Event) - 菜单按钮点击事件对象。
     * 返回值说明：无
     */
    showMenu(event) {
        if (State.repoPermission !== 'admin') return;
        const menuBtn = document.getElementById('btn-menu');
        if (!menuBtn) return;
        const rect = menuBtn.getBoundingClientRect();

        let menu = document.getElementById('album-action-menu');
        if (!menu) {
            menu = document.createElement('div');
            menu.id = 'album-action-menu';
            menu.className = 'dropdown-menu';
            document.body.appendChild(menu);

            // 点击菜单外部时关闭
            document.addEventListener('click', (e) => {
                if (!menu.contains(e.target) && !menuBtn.contains(e.target)) {
                    menu.classList.remove('show');
                }
            });
        }

        // 再次点击菜单按钮时关闭
        if (menu.classList.contains('show')) {
            menu.classList.remove('show');
            return;
        }

        const isScanning = App.isScanning();
        const isMetadataRefresh = isScanning && State.scanTaskType === 'metadata';
        const scanText = isScanning
            ? I18nManager.t(isMetadataRefresh ? 'file_repo.menu_stop_metadata' : 'file_repo.menu_stop_scan')
            : I18nManager.t('file_repo.menu_start_scan');
        const scanClass = isScanning ? 'menu-item text-danger' : 'menu-item';

        menu.textContent = '';
        const refreshItem = document.createElement('div');
        refreshItem.className = isScanning ? 'menu-item disabled' : 'menu-item';
        refreshItem.id = 'album-menu-refresh-metadata';
        refreshItem.textContent = I18nManager.t('file_repo.menu_refresh_metadata');
        refreshItem.setAttribute('aria-disabled', String(isScanning));
        menu.appendChild(refreshItem);

        refreshItem.onclick = () => {
            menu.classList.remove('show');
            if (!App.isScanning()) App.confirmMetadataRefresh();
        };

        const scanItem = document.createElement('div');
        scanItem.className = scanClass;
        scanItem.id = 'album-menu-scan';
        scanItem.textContent = scanText;
        menu.appendChild(scanItem);

        scanItem.onclick = () => {
            menu.classList.remove('show');
            if (App.isScanning()) App.handleStopScan();
            else App.confirmStartScan();
        };

        menu.style.top = `${rect.bottom + 5}px`;
        menu.style.left = `${rect.right - 160}px`;
        menu.classList.add('show');
    },

    /**
     * 用途说明：扫描期间隐藏相册内容，仅保留进度遮罩，与文件管理页面的展示逻辑一致。
     * 入参说明：isScanning (boolean) - 是否正在扫描。
     * 返回值说明：无
     */
    toggleScanUI(isScanning) {
        const pageContent = this.elements.pageContent;
        if (!pageContent) return;
        pageContent.style.visibility = isScanning ? 'hidden' : 'visible';
    },

    /**
     * 用途说明：显示扫描进度遮罩；若遮罩此前被隐藏，则重新设为显示，保证多次扫描都能看到进度。
     * 入参说明：无
     * 返回值说明：无
     */
    showScanProgress() {
        const progressText = State.scanTaskType === 'metadata'
            ? I18nManager.t('file_repo.metadata_refreshing')
            : I18nManager.t('file_repo.scanning');
        UIComponents.showProgressBar('#album-main-content', progressText);
        const overlay = document.querySelector('#album-main-content .common-progress-overlay');
        if (overlay) overlay.style.display = 'flex';
    },

    /**
     * 用途说明：绑定时间轴上方的媒体类型筛选下拉框，切换后重置分页并按类型重新加载。
     * 入参说明：无
     * 返回值说明：无
     */
    bindTypeFilter() {
        const select = this.elements.typeFilter;
        if (!select) return;
        select.value = State.fileType;
        select.onchange = () => {
            State.fileType = select.value || '';
            App.loadFirstPage();
        };
    },

    /**
     * 用途说明：绑定相册排序下拉框，时间默认倒序、文件名默认升序、文件大小默认倒序。
     * 入参说明：无
     * 返回值说明：无
     */
    bindSortFilter() {
        const select = this.elements.sortFilter;
        if (!select) return;
        select.value = State.sortBy;
        select.onchange = () => {
            const sortBy = select.value;
            if (!['album_time', 'file_name', 'file_size'].includes(sortBy)) return;
            State.sortBy = sortBy;
            State.orderAsc = sortBy === 'file_name';
            this.updateAxisMode();
            App.loadFirstPage();
        };
    },

    /**
     * 用途说明：绑定标尺侧边栏开关，点击后仅切换侧边栏显隐，不改变当前排序与筛选条件。
     * 入参说明：无
     * 返回值说明：无
     */
    bindSidebarToggle() {
        const button = this.elements.sidebarToggle;
        if (!button) return;
        button.onclick = () => {
            State.sidebarVisible = !State.sidebarVisible;
            this.updateSidebarVisibility();
        };
    },

    /**
     * 用途说明：同步侧边栏、布局与开关状态；文件大小排序无标尺，自动隐藏侧边栏和开关。
     * 入参说明：无
     * 返回值说明：无
     */
    updateSidebarVisibility() {
        const hasAxis = State.sortBy !== 'file_size';
        const visible = hasAxis && State.sidebarVisible;
        if (this.elements.timeline) this.elements.timeline.classList.toggle('hidden', !visible);
        if (this.elements.layout) this.elements.layout.classList.toggle('sidebar-hidden', !visible);
        const button = this.elements.sidebarToggle;
        if (button) {
            button.classList.toggle('hidden', !hasAxis);
            button.classList.toggle('is-collapsed', !State.sidebarVisible);
            button.setAttribute('aria-expanded', String(visible));
            button.title = I18nManager.t(State.sidebarVisible ? 'album.sidebar_hide' : 'album.sidebar_show');
        }
        this.updateTimelineActive();
    },

    /**
     * 用途说明：根据排序方式切换标尺：时间显示时间轴、文件名显示字母尺、文件大小完全隐藏标尺与标题。
     * 入参说明：无
     * 返回值说明：无
     */
    updateAxisMode() {
        const isSize = State.sortBy === 'file_size';
        if (this.elements.axis) this.elements.axis.classList.toggle('hidden', isSize);
        if (this.elements.axisTitle) {
            const labelKey = State.sortBy === 'file_name' ? 'album.letter_axis_label' : 'album.time_axis_label';
            this.elements.axisTitle.textContent = I18nManager.t(labelKey);
        }
        if (this.elements.timeline) {
            const hintKey = State.sortBy === 'file_name' ? 'album.letter_axis_title' : 'album.timeline_title';
            this.elements.timeline.title = I18nManager.t(hintKey);
        }
        this.updateSidebarVisibility();
        this.rebuildTimeline();
    },

    /**
     * 用途说明：初始化无限滚动哨兵监听与卡片缩略图懒加载监听。
     * 入参说明：无
     * 返回值说明：无
     */
    initObservers() {
        const scrollRoot = document.querySelector('.main-content');

        State.sentinelObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) App.loadNextPage();
            });
        }, { root: scrollRoot, rootMargin: '400px 0px' });
        if (this.elements.sentinel) State.sentinelObserver.observe(this.elements.sentinel);

        State.cardObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (!entry.isIntersecting) return;
                const card = entry.target;
                const info = State.cardMap.get(card.getAttribute('data-path'));
                if (info && !info.item.thumbnail_path && !State.ensureRequested.has(info.item.file_path)) {
                    App.enqueueThumbnail(info.item.file_path);
                }
                State.cardObserver.unobserve(card);
            });
        }, { root: scrollRoot, rootMargin: '300px 0px' });

        // 监听滚动容器的滚动，节流更新动态标尺当前所在刻度
        // 说明：使用 setTimeout 而非 requestAnimationFrame，避免页面处于后台时帧回调暂停导致刻度长期不更新
        if (scrollRoot) {
            let scrollThrottled = false;
            scrollRoot.addEventListener('scroll', () => {
                if (scrollThrottled) return;
                scrollThrottled = true;
                window.setTimeout(() => {
                    scrollThrottled = false;
                    UIController.updateTimelineActive();
                }, 80);
            }, { passive: true });
        }
    },

    /**
     * 用途说明：绑定预览弹窗的按钮与键盘事件。
     * 入参说明：无
     * 返回值说明：无
     */
    bindPreviewEvents() {
        if (this.elements.previewCloseBtn) {
            this.elements.previewCloseBtn.onclick = () => this.closePreview();
        }
        if (this.elements.previewPrevBtn) {
            this.elements.previewPrevBtn.onclick = () => this.previewStep(-1);
        }
        if (this.elements.previewNextBtn) {
            this.elements.previewNextBtn.onclick = () => this.previewStep(1);
        }
        if (this.elements.previewDownloadBtn) {
            this.elements.previewDownloadBtn.onclick = () => {
                const item = State.items[State.previewIndex];
                if (item) App.downloadFiles([item.file_path]);
            };
        }
        if (this.elements.previewSelectBtn) {
            this.elements.previewSelectBtn.onclick = () => {
                const item = State.items[State.previewIndex];
                if (!item) return;
                // 预览页同样支持选中/取消选中，与列表卡片的选中状态保持同步
                App.toggleSelection(item.file_path, !State.selected.has(item.file_path));
                this.syncPreviewSelectionState();
            };
        }
        if (this.elements.previewDeleteBtn) {
            this.elements.previewDeleteBtn.onclick = () => {
                const item = State.items[State.previewIndex];
                if (item) App.deleteFiles([item.file_path], true);
            };
        }
        if (this.elements.previewDetailBtn) {
            this.elements.previewDetailBtn.onclick = () => {
                const item = State.items[State.previewIndex];
                if (item) this.showDetail(item);
            };
        }
        if (this.elements.detailCloseBtn) {
            this.elements.detailCloseBtn.onclick = () => this.closeDetail();
        }
        if (this.elements.previewMask) {
            this.elements.previewMask.addEventListener('click', (e) => {
                // 点击遮罩空白处（非媒体、非按钮）关闭预览
                if (e.target === this.elements.previewMask) this.closePreview();
            });
        }
        document.addEventListener('keydown', (e) => {
            // 详情侧边栏打开时，Esc 优先关闭侧边栏
            if (e.key === 'Escape' && this.elements.detailPanel
                && !this.elements.detailPanel.classList.contains('hidden')) {
                this.closeDetail();
                return;
            }
            if (State.previewIndex < 0) return;
            if (e.key === 'Escape') this.closePreview();
            else if (e.key === 'ArrowLeft') this.previewStep(-1);
            else if (e.key === 'ArrowRight') this.previewStep(1);
        });
    },

    /**
     * 用途说明：绑定详情侧边栏左边缘拖动调整宽度事件，宽度限制在页面宽度的 20% 至 80% 之间。
     * 入参说明：无
     * 返回值说明：无
     */
    bindDetailResize() {
        const handle = this.elements.detailResize;
        const panel = this.elements.detailPanel;
        if (!handle || !panel) return;

        // 按页面宽度 20%～80% 夹取后应用到侧边栏
        const applyWidth = (width) => {
            const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 0;
            let targetWidth = width;
            if (viewportWidth > 0) {
                const minWidth = viewportWidth * 0.2;
                const maxWidth = viewportWidth * 0.8;
                targetWidth = Math.min(maxWidth, Math.max(minWidth, width));
            }
            State.detailWidth = targetWidth;
            panel.style.width = `${Math.round(targetWidth)}px`;
        };

        handle.addEventListener('pointerdown', (e) => {
            if (panel.classList.contains('hidden')) return;
            State.detailResizing = true;
            State.detailDragStartX = e.clientX;
            State.detailDragStartWidth = panel.getBoundingClientRect().width;
            handle.setPointerCapture(e.pointerId);
            e.preventDefault();
        });

        handle.addEventListener('pointermove', (e) => {
            if (!State.detailResizing) return;
            // 向左拖动（clientX 减小）时加宽，向右拖动时收窄
            applyWidth(State.detailDragStartWidth + (State.detailDragStartX - e.clientX));
        });

        const stopResize = (e) => {
            if (!State.detailResizing) return;
            State.detailResizing = false;
            if (handle.hasPointerCapture(e.pointerId)) {
                handle.releasePointerCapture(e.pointerId);
            }
        };
        handle.addEventListener('pointerup', stopResize);
        handle.addEventListener('pointercancel', stopResize);

        // 窗口尺寸变化时重新夹取，避免超出 20%～80% 范围
        window.addEventListener('resize', () => {
            if (State.detailWidth > 0 && !panel.classList.contains('hidden')) {
                applyWidth(State.detailWidth);
            }
        });
    },

    /**
     * 用途说明：根据媒体数据创建瀑布流卡片（含缩略图/占位图、勾选框、下载与删除按钮）。
     * 入参说明：item (Object) - 媒体项 {file_path, file_name, file_type, thumbnail_path}。
     * 返回值说明：HTMLElement - 创建好的卡片元素。
     */
    createCard(item) {
        const card = document.createElement('article');
        card.className = 'album-card';
        card.setAttribute('data-path', item.file_path);

        const wrap = document.createElement('div');
        wrap.className = 'album-thumb-wrap';

        const placeholder = document.createElement('div');
        placeholder.className = 'album-placeholder';
        const placeholderIcon = document.createElement('span');
        placeholderIcon.className = `album-placeholder-icon theme-icon ${item.file_type === 'video' ? 'icon-video' : 'icon-image'}`;
        placeholderIcon.setAttribute('aria-hidden', 'true');
        const placeholderText = document.createElement('span');
        placeholderText.className = 'album-placeholder-text';
        placeholderText.textContent = I18nManager.t('album.thumbnail_generating');
        placeholder.appendChild(placeholderIcon);
        placeholder.appendChild(placeholderText);

        const img = document.createElement('img');
        img.className = 'album-thumb hidden';
        img.alt = item.file_name;
        // 注意：此处不能使用 loading="lazy"。
        // 缩略图在加载完成前处于 hidden（display:none）状态，而浏览器对 display:none 的懒加载图片
        // 不会发起网络请求，导致 onload 永不触发、占位文案永远停留在“缩略图生成中”。
        // 按需加载已由卡片可见性观察器（cardObserver）控制，这里无需再懒加载。
        img.onerror = () => this.handleThumbError(item.file_path);
        img.onload = () => {
            img.classList.remove('hidden');
            placeholder.classList.add('hidden');
        };

        wrap.appendChild(placeholder);
        wrap.appendChild(img);

        if (item.file_type === 'video') {
            const badge = document.createElement('span');
            badge.className = 'album-type-badge';
            badge.textContent = I18nManager.t('album.video_badge');
            wrap.appendChild(badge);
        }

        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.className = 'album-check';
        checkbox.title = I18nManager.t('album.select_item');
        checkbox.checked = State.selected.has(item.file_path);
        checkbox.onclick = (e) => e.stopPropagation();
        checkbox.onchange = (e) => App.toggleSelection(item.file_path, e.target.checked);
        wrap.appendChild(checkbox);

        const actions = document.createElement('div');
        actions.className = 'album-actions';
        const downloadBtn = document.createElement('button');
        downloadBtn.type = 'button';
        downloadBtn.className = 'album-action-btn';
        downloadBtn.title = I18nManager.t('album.download');
        const downloadIcon = document.createElement('span');
        downloadIcon.className = 'theme-icon icon-download';
        downloadIcon.setAttribute('aria-hidden', 'true');
        downloadBtn.appendChild(downloadIcon);
        downloadBtn.onclick = (e) => {
            e.stopPropagation();
            App.downloadFiles([item.file_path]);
        };
        actions.appendChild(downloadBtn);
        if (State.repoPermission === 'admin') {
            const deleteBtn = document.createElement('button');
            deleteBtn.type = 'button';
            deleteBtn.className = 'album-action-btn album-action-danger';
            deleteBtn.title = I18nManager.t('album.delete');
            const deleteIcon = document.createElement('span');
            deleteIcon.className = 'theme-icon icon-trash';
            deleteIcon.setAttribute('aria-hidden', 'true');
            deleteBtn.appendChild(deleteIcon);
            deleteBtn.onclick = (e) => {
                e.stopPropagation();
                App.deleteFiles([item.file_path], false);
            };
            actions.appendChild(deleteBtn);
        }
        wrap.appendChild(actions);

        // 文件名行：文件名 + 详情按钮（按钮位于名称右侧）
        const nameRow = document.createElement('div');
        nameRow.className = 'album-name-row';

        const name = document.createElement('div');
        name.className = 'album-name';
        name.textContent = item.file_name;

        const detailBtn = document.createElement('button');
        detailBtn.type = 'button';
        detailBtn.className = 'album-detail-trigger';
        detailBtn.title = I18nManager.t('album.detail_open');
        const detailIcon = document.createElement('span');
        detailIcon.className = 'theme-icon icon-info';
        detailIcon.setAttribute('aria-hidden', 'true');
        detailBtn.appendChild(detailIcon);
        detailBtn.onclick = (e) => {
            e.stopPropagation();
            this.showDetail(item);
        };
        nameRow.appendChild(name);
        nameRow.appendChild(detailBtn);

        card.appendChild(wrap);
        card.appendChild(nameRow);
        card.onclick = () => this.openPreview(item.file_path);

        State.cardMap.set(item.file_path, {
            card: card,
            item: item,
            img: img,
            placeholder: placeholder,
            placeholderText: placeholderText
        });

        if (item.thumbnail_path) {
            this.applyThumbnail(item.file_path, item.thumbnail_path);
        }
        if (State.selected.has(item.file_path)) card.classList.add('selected');

        if (State.cardObserver) State.cardObserver.observe(card);
        return card;
    },

    /**
     * 用途说明：将缩略图地址应用到卡片，并切换显示图片。
     * 入参说明：filePath (string) - 媒体路径；thumbPath (string) - 缩略图物理路径。
     * 返回值说明：无
     */
    applyThumbnail(filePath, thumbPath) {
        const info = State.cardMap.get(filePath);
        if (!info) return;
        info.item.thumbnail_path = thumbPath;
        info.placeholderText.textContent = I18nManager.t('album.thumbnail_generating');
        info.img.src = AlbumBrowseRequest.buildThumbnailUrl(thumbPath);
    },

    /**
     * 用途说明：缩略图加载失败时展示占位图，并最多触发一次重新生成。
     * 入参说明：filePath (string) - 媒体路径。
     * 返回值说明：无
     */
    handleThumbError(filePath) {
        const info = State.cardMap.get(filePath);
        if (!info) return;
        info.img.classList.add('hidden');
        info.placeholder.classList.remove('hidden');
        info.placeholderText.textContent = I18nManager.t('album.thumbnail_failed');

        // 旧缩略图路径失效时允许重新请求一次，避免死循环
        if (!info.card.dataset.retried) {
            info.card.dataset.retried = '1';
            info.item.thumbnail_path = null;
            State.ensureRequested.delete(filePath);
            App.enqueueThumbnail(filePath);
        }
    },

    /**
     * 用途说明：缩略图生成失败时更新占位文案。
     * 入参说明：filePath (string) - 媒体路径。
     * 返回值说明：无
     */
    markThumbnailFailed(filePath) {
        const info = State.cardMap.get(filePath);
        if (!info || info.item.thumbnail_path) return;
        info.img.classList.add('hidden');
        info.placeholder.classList.remove('hidden');
        info.placeholderText.textContent = I18nManager.t('album.thumbnail_failed');
    },

    /**
     * 用途说明：解析媒体项所属分组；时间使用拍摄/修改日期，文件名使用后端返回的拼音首字母，大小使用统一分组。
     * 入参说明：item (Object) - 媒体项，包含时间字段与 filename_initial。
     * 返回值说明：string - 当前排序方式对应的分组键。
     */
    resolveGroupKey(item) {
        if (State.sortBy === 'file_name') {
            const initial = String(item.filename_initial || '').toUpperCase();
            return /^[A-Z]$/.test(initial) ? initial : '#';
        }
        if (State.sortBy === 'file_size') return 'size';
        const rawTime = item.file_exif_time || item.file_mtime || item.scan_time || '';
        const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(rawTime);
        return match ? match[1] + '-' + match[2] + '-' + match[3] : 'unknown';
    },

    /**
     * 用途说明：生成当前排序方式的分组标题，支持本地化日期、字母与文件大小标题。
     * 入参说明：key (string) - 当前排序方式对应的分组键。
     * 返回值说明：string - 本地化后的分组标题。
     */
    buildGroupTitle(key) {
        if (State.sortBy === 'file_size') return I18nManager.t('album.size_group_title');
        if (State.sortBy === 'file_name') return key;
        if (key === 'unknown') return I18nManager.t('album.unknown_date');
        const parts = key.split('-');
        const year = parseInt(parts[0], 10);
        const month = parseInt(parts[1], 10);
        const day = parseInt(parts[2], 10);
        if (I18nManager.currentLang === 'zh') {
            return year + '年' + month + '月' + day + '日';
        }
        return new Intl.DateTimeFormat('en-US', {
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        }).format(new Date(year, month - 1, day));
    },

    /**
     * 用途说明：确保指定分组的容器（标题 + 多列瀑布流网格）已创建，并按接口顺序追加新分组。
     * 入参说明：key (string) - 当前排序方式对应的分组键。
     * 返回值说明：Object - 分组信息 { key, section, grid, count }。
     */
    ensureGroup(key) {
        const existing = State.groupMap.get(key);
        if (existing) return existing;

        const section = document.createElement('section');
        section.className = 'album-group';
        section.setAttribute('data-key', key);

        const title = document.createElement('h2');
        title.className = 'album-group-title';
        title.textContent = this.buildGroupTitle(key);

        const grid = document.createElement('div');
        grid.className = 'album-group-grid';

        section.appendChild(title);
        section.appendChild(grid);
        if (this.elements.waterfall) this.elements.waterfall.appendChild(section);

        const groupInfo = { key: key, section: section, grid: grid, count: 0 };
        State.groupMap.set(key, groupInfo);
        State.groupKeys.push(key);
        return groupInfo;
    },

    /**
     * 用途说明：重建动态标尺：时间排序生成年份/月份/日期刻度，文件名排序生成首字母刻度。
     * 入参说明：无
     * 返回值说明：无
     */
    rebuildTimeline() {
        const ticksHost = this.elements.timelineTicks;
        if (!ticksHost) return;
        // 仅清空刻度容器，保留顶部的排序与媒体类型筛选下拉框
        ticksHost.textContent = '';
        State.timelineTicks = [];
        ticksHost.classList.toggle('hidden', State.groupKeys.length === 0);
        if (State.groupKeys.length === 0 || State.sortBy === 'file_size') return;

        const track = document.createElement('div');
        track.className = 'album-timeline-track';

        if (State.sortBy === 'file_name') {
            State.groupKeys.forEach(key => {
                track.appendChild(this.createTimelineTick('letter', key, key, key, '', ''));
            });
            ticksHost.appendChild(track);
            this.updateTimelineActive();
            return;
        }

        let prevYear = '';
        let prevMonth = '';
        State.groupKeys.forEach(key => {
            let year = '';
            let month = '';
            if (key !== 'unknown') {
                const parts = key.split('-');
                year = parts[0];
                month = parts[1];
            }

            // 年份刻度：每年只出现一次，字号最大并显示具体年份
            if (key !== 'unknown' && year !== prevYear) {
                const yearLabel = I18nManager.currentLang === 'zh' ? year + '年' : year;
                track.appendChild(this.createTimelineTick('year', key, yearLabel, this.buildGroupTitle(key), year, month));
                prevYear = year;
                prevMonth = '';
            }

            // 月份刻度：每年内每月只出现一次，字号次之并显示月份
            if (key !== 'unknown' && month !== prevMonth) {
                const monthLabel = I18nManager.currentLang === 'zh'
                    ? parseInt(month, 10) + '月'
                    : new Intl.DateTimeFormat('en-US', { month: 'short' })
                        .format(new Date(parseInt(year, 10), parseInt(month, 10) - 1, 1));
                track.appendChild(this.createTimelineTick('month', key, monthLabel, this.buildGroupTitle(key), year, month));
                prevMonth = month;
            }

            // 日刻度：仅显示圆点，不显示日期文字，悬浮提示完整日期
            track.appendChild(this.createTimelineTick('day', key, '', this.buildGroupTitle(key), year, month));
        });

        ticksHost.appendChild(track);
        this.updateTimelineActive();
    },

    /**
     * 用途说明：创建单个动态标尺刻度元素并绑定跳转事件。
     * 入参说明：
     *   level (string) - 刻度层级：year / month / day / letter。
     *   anchorKey (string) - 点击后滚动到的分组键。
     *   label (string) - 刻度文案（日刻度为空字符串）。
     *   title (string) - 悬浮提示文案。
     *   year (string) - 所属年份（unknown 分组为空）。
     *   month (string) - 所属月份（unknown 分组为空）。
     * 返回值说明：HTMLElement - 刻度元素。
     */
    createTimelineTick(level, anchorKey, label, title, year, month) {
        const tick = document.createElement('div');
        tick.className = 'album-timeline-tick album-timeline-tick-' + level;
        tick.setAttribute('data-key', anchorKey);
        if (title) tick.title = title;
        if (label) {
            const labelEl = document.createElement('span');
            labelEl.className = 'album-timeline-label';
            labelEl.textContent = label;
            tick.appendChild(labelEl);
        }
        tick.onclick = () => this.scrollToGroup(anchorKey);
        State.timelineTicks.push({
            el: tick,
            level: level,
            key: anchorKey,
            year: year || '',
            month: month || ''
        });
        return tick;
    },

    /**
     * 用途说明：根据当前滚动位置高亮标尺刻度：时间轴同步年份/月份上下文，字母尺仅高亮当前首字母。
     * 入参说明：无
     * 返回值说明：无
     */
    updateTimelineActive() {
        const scrollRoot = document.querySelector('.main-content');
        if (!scrollRoot || State.groupKeys.length === 0) return;

        const rootTop = scrollRoot.getBoundingClientRect().top;
        let activeKey = State.groupKeys[0];
        State.groupKeys.forEach(key => {
            const group = State.groupMap.get(key);
            if (!group) return;
            if (group.section.getBoundingClientRect().top - rootTop <= 96) activeKey = key;
        });
        State.activeGroupKey = activeKey;

        let activeYear = '';
        let activeMonth = '';
        if (State.sortBy === 'album_time' && activeKey !== 'unknown') {
            const parts = activeKey.split('-');
            activeYear = parts[0];
            activeMonth = parts[1];
        }

        State.timelineTicks.forEach(tick => {
            let isActive = tick.key === activeKey;
            let isContext = false;
            if (tick.level === 'year') {
                isContext = tick.year === activeYear;
            } else if (tick.level === 'month') {
                isContext = tick.year === activeYear && tick.month === activeMonth;
            }
            tick.el.classList.toggle('is-active', isActive);
            tick.el.classList.toggle('is-context', isContext);
        });
    },

    /**
     * 用途说明：点击动态标尺刻度后平滑滚动到对应分组。
     * 入参说明：key (string) - 目标分组键。
     * 返回值说明：无
     */
    scrollToGroup(key) {
        const group = State.groupMap.get(key);
        const scrollRoot = document.querySelector('.main-content');
        if (!group || !scrollRoot) return;
        const offset = group.section.getBoundingClientRect().top
            - scrollRoot.getBoundingClientRect().top
            + scrollRoot.scrollTop
            - 12;
        scrollRoot.scrollTo({ top: Math.max(0, offset), behavior: 'smooth' });
    },

    /**
     * 用途说明：移除已清空的分组容器并重建动态标尺。
     * 入参说明：key (string) - 待移除的分组键。
     * 返回值说明：无
     */
    removeGroup(key) {
        const group = State.groupMap.get(key);
        if (!group) return;
        if (group.section.parentNode) group.section.parentNode.removeChild(group.section);
        State.groupMap.delete(key);
        const index = State.groupKeys.indexOf(key);
        if (index >= 0) State.groupKeys.splice(index, 1);
        this.rebuildTimeline();
    },

    /**
     * 用途说明：渲染一页媒体卡片，按当前排序分组并严格沿用接口返回顺序追加到瀑布流。
     * 入参说明：list (Array<Object>) - 媒体项数组。
     * 返回值说明：无
     */
    appendItems(list) {
        if (!this.elements.waterfall) return;
        const previousGroupCount = State.groupKeys.length;
        list.forEach(item => {
            const groupKey = this.resolveGroupKey(item);
            const group = this.ensureGroup(groupKey);
            const card = this.createCard(item);
            const info = State.cardMap.get(item.file_path);
            if (info) info.groupKey = groupKey;
            group.grid.appendChild(card);
            group.count += 1;
        });
        if (State.groupKeys.length !== previousGroupCount) this.rebuildTimeline();
        this.updateTimelineActive();
    },

    /**
     * 用途说明：重置列表 DOM、卡片缓存与排序分组（用于搜索、切换排序或首次加载）。
     * 入参说明：无
     * 返回值说明：无
     */
    clearList() {
        if (this.elements.waterfall) this.elements.waterfall.textContent = '';
        State.cardMap.clear();
        State.groupMap.clear();
        State.groupKeys = [];
        State.timelineTicks = [];
        this.rebuildTimeline();
    },

    /**
     * 用途说明：根据文件路径批量移除卡片、空分组与选中状态。
     * 入参说明：filePaths (Array<string>) - 待移除的文件路径列表。
     * 返回值说明：无
     */
    removeByPaths(filePaths) {
        filePaths.forEach(filePath => {
            const info = State.cardMap.get(filePath);
            if (info) {
                if (info.card.parentNode) info.card.parentNode.removeChild(info.card);
                const group = State.groupMap.get(info.groupKey);
                if (group) {
                    group.count -= 1;
                    if (group.count <= 0) this.removeGroup(info.groupKey);
                }
            }
            State.cardMap.delete(filePath);
            State.selected.delete(filePath);
            State.ensureRequested.delete(filePath);
        });
        this.updateEmptyState();
    },

    /**
     * 用途说明：刷新空数据与“没有更多”提示。
     * 入参说明：无
     * 返回值说明：无
     */
    updateEmptyState() {
        const isEmpty = State.items.length === 0;
        if (this.elements.empty) this.elements.empty.classList.toggle('hidden', !isEmpty);
        if (this.elements.endTip) {
            const showEnd = !isEmpty && !State.hasMore && !State.loading;
            this.elements.endTip.classList.toggle('hidden', !showEnd);
        }
    },

    /**
     * 用途说明：更新多选操作栏的显示状态与计数。
     * 入参说明：无
     * 返回值说明：无
     */
    updateSelectionBar() {
        const count = State.selected.size;
        if (this.elements.selectionBar) {
            this.elements.selectionBar.classList.toggle('hidden', count === 0);
        }
        if (this.elements.selectedCount) {
            this.elements.selectedCount.textContent = I18nManager.t('album.selected_count', { count: count });
        }
        if (this.elements.deleteSelectedBtn) {
            this.elements.deleteSelectedBtn.classList.toggle('hidden', State.repoPermission !== 'admin');
        }
        // 选中数量变化时同步刷新预览页的选中数量展示
        this.syncPreviewSelectionState();
    },

    /**
     * 用途说明：设置指定卡片的选中态。
     * 入参说明：filePath (string) - 媒体路径；selected (boolean) - 是否选中。
     * 返回值说明：无
     */
    setCardSelected(filePath, selected) {
        const info = State.cardMap.get(filePath);
        if (!info) return;
        info.card.classList.toggle('selected', selected);
        const checkbox = info.card.querySelector('.album-check');
        if (checkbox) checkbox.checked = selected;
    },

    /**
     * 用途说明：打开媒体预览弹窗。
     * 入参说明：filePath (string) - 媒体路径。
     * 返回值说明：无
     */
    openPreview(filePath) {
        const index = State.items.findIndex(item => item.file_path === filePath);
        if (index < 0) return;
        this.showPreview(index);
    },

    /**
     * 用途说明：按索引展示预览内容（图片或视频）。
     * 入参说明：index (number) - State.items 中的索引。
     * 返回值说明：无
     */
    showPreview(index) {
        if (index < 0 || index >= State.items.length) return;
        State.previewIndex = index;
        const item = State.items[index];

        if (this.elements.previewMask) this.elements.previewMask.classList.remove('hidden');
        // 切换预览内容时关闭旧详情，避免展示上一条媒体的信息
        this.closeDetail();
        document.body.classList.add('album-preview-open');
        if (this.elements.previewName) this.elements.previewName.textContent = item.file_name;

        const body = this.elements.previewBody;
        if (body) {
            body.textContent = '';
            if (item.file_type === 'video') {
                const video = document.createElement('video');
                video.className = 'album-preview-media';
                video.controls = true;
                // 预览视频不自动播放，由用户手动点击播放
                video.autoplay = false;
                video.preload = 'metadata';
                video.playsInline = true;
                video.src = AlbumBrowseRequest.buildMediaUrl(item.file_path);
                body.appendChild(video);
            } else {
                const img = document.createElement('img');
                img.className = 'album-preview-media';
                img.alt = item.file_name;
                img.src = AlbumBrowseRequest.buildMediaUrl(item.file_path);
                body.appendChild(img);
            }
        }

        const hasMultiple = State.items.length > 1;
        if (this.elements.previewPrevBtn) this.elements.previewPrevBtn.classList.toggle('hidden', !hasMultiple);
        if (this.elements.previewNextBtn) this.elements.previewNextBtn.classList.toggle('hidden', !hasMultiple);
        this.syncPreviewSelectionState();
    },

    /**
     * 用途说明：同步预览页选中按钮的外观与提示文案（已选中高亮，提示切换为取消选中）。
     * 入参说明：无
     * 返回值说明：无
     */
    syncPreviewSelectionState() {
        const button = this.elements.previewSelectBtn;
        const item = State.items[State.previewIndex];
        if (!button || !item) return;
        const isSelected = State.selected.has(item.file_path);
        button.classList.toggle('is-selected', isSelected);
        button.title = I18nManager.t(isSelected ? 'album.deselect_item' : 'album.select_item');

        // 更新选中按钮旁的选中数量：无选中项时隐藏
        const countEl = this.elements.previewSelectedCount;
        if (countEl) {
            const count = State.selected.size;
            countEl.textContent = I18nManager.t('album.selected_count', { count: count });
            countEl.classList.toggle('hidden', count === 0);
        }
    },

    /**
     * 用途说明：打开右侧详情侧边栏，填充当前媒体文件的基础信息。
     * 入参说明：item (Object) - 媒体项 {file_name, file_path, file_exif_time, file_mtime, file_size, file_location}。
     * 返回值说明：无
     */
    showDetail(item) {
        if (!item || !this.elements.detailPanel) return;
        const unknownText = I18nManager.t('album.detail_unknown');
        const setText = (element, value) => {
            if (element) element.textContent = value || unknownText;
        };

        setText(this.elements.detailName, item.file_name);
        setText(this.elements.detailPath, item.file_path);
        setText(this.elements.detailCaptureTime, item.file_exif_time);
        setText(this.elements.detailMtime, item.file_mtime);
        setText(this.elements.detailSize, item.file_size ? this.formatFileSize(item.file_size) : '');
        setText(this.elements.detailLocation, item.file_location);
        this.elements.detailPanel.classList.remove('hidden');
    },

    /**
     * 用途说明：关闭右侧详情侧边栏。
     * 入参说明：无
     * 返回值说明：无
     */
    closeDetail() {
        if (this.elements.detailPanel) this.elements.detailPanel.classList.add('hidden');
    },

    /**
     * 用途说明：将字节数格式化为易读的文件大小文本。
     * 入参说明：bytes (number) - 文件大小（字节）。
     * 返回值说明：string - 形如 '1.25 MB' 的文本。
     */
    formatFileSize(bytes) {
        const size = Number(bytes) || 0;
        if (size <= 0) return '0 B';
        const units = ['B', 'KB', 'MB', 'GB', 'TB'];
        const index = Math.min(units.length - 1, Math.floor(Math.log(size) / Math.log(1024)));
        const value = size / Math.pow(1024, index);
        return `${index === 0 ? value : value.toFixed(2)} ${units[index]}`;
    },

    /**
     * 用途说明：切换上一张/下一张（循环）。
     * 入参说明：step (number) - -1 表示上一张，1 表示下一张。
     * 返回值说明：无
     */
    previewStep(step) {
        if (State.previewIndex < 0 || State.items.length <= 1) return;
        const nextIndex = (State.previewIndex + step + State.items.length) % State.items.length;
        this.showPreview(nextIndex);
    },

    /**
     * 用途说明：关闭预览弹窗并停止视频播放。
     * 入参说明：无
     * 返回值说明：无
     */
    closePreview() {
        State.previewIndex = -1;
        if (this.elements.previewMask) this.elements.previewMask.classList.add('hidden');
        if (this.elements.previewBody) this.elements.previewBody.textContent = '';
        // 预览关闭时一并关闭详情侧边栏
        this.closeDetail();
        document.body.classList.remove('album-preview-open');
    }
};

// --- 应用逻辑主入口 ---
const App = {
    /**
     * 用途说明：初始化应用并加载首屏数据。
     * 入参说明：无
     * 返回值说明：无
     */
    init() {
        UIController.init();
        this.bindToolbarActions();
        API.getCurrentUser(
            (data) => {
                State.repoPermission = data.repo_permission || '';
                UIController.applyPermissionUI();
                this.loadFirstPage();
                if (State.repoPermission === 'admin') this.checkScanStatus();
            },
            () => {
                // 权限获取失败时按只读成员处理，避免误展示删除入口
                State.repoPermission = '';
                UIController.applyPermissionUI();
                this.loadFirstPage();
            }
        );
    },

    /**
     * 用途说明：判断当前是否处于索引扫描中。
     * 入参说明：无
     * 返回值说明：boolean - 正在扫描返回 true，否则返回 false。
     */
    isScanning() {
        return State.scanInterval !== null;
    },

    /**
     * 用途说明：弹出确认框，询问是否补全当前索引中缺少的媒体信息。
     * 入参说明：无
     * 返回值说明：无
     */
    confirmMetadataRefresh() {
        if (State.repoPermission !== 'admin' || this.isScanning()) return;
        UIComponents.showConfirmModal({
            title: I18nManager.t('file_repo.metadata_refresh_confirm_title'),
            message: I18nManager.t('file_repo.metadata_refresh_confirm_msg'),
            confirmText: I18nManager.t('file_repo.menu_refresh_metadata'),
            onConfirm: () => this.handleMetadataRefresh()
        });
    },

    /**
     * 用途说明：启动缺失信息补全任务，并复用索引任务的进度展示与轮询。
     * 入参说明：无
     * 返回值说明：无
     */
    handleMetadataRefresh() {
        State.scanTaskType = 'metadata';
        API.refreshMetadata(
            () => {
                Toast.show(I18nManager.t('file_repo.metadata_refresh_started'));
                UIController.toggleScanUI(true);
                UIController.showScanProgress();
                this.startScanPolling();
            },
            (msg) => {
                State.scanTaskType = '';
                Toast.show(msg);
            }
        );
    },

    /**
     * 用途说明：弹出确认框询问是否开始建立索引，支持选择重新扫描全部索引。
     * 入参说明：无
     * 返回值说明：无
     */
    confirmStartScan() {
        if (State.repoPermission !== 'admin') return;
        UIComponents.showConfirmModal({
            title: I18nManager.t('file_repo.scan_confirm_title'),
            message: I18nManager.t('file_repo.scan_confirm_msg'),
            checkbox: { label: I18nManager.t('file_repo.scan_rebuild_label'), checked: false },
            confirmText: I18nManager.t('file_repo.menu_start_scan'),
            onConfirm: (fullScan) => this.handleStartScan(fullScan)
        });
    },

    /**
     * 用途说明：调用接口启动索引扫描任务，并进入与文件管理页面一致的进度展示状态。
     * 入参说明：fullScan (boolean) - 是否进行全量扫描。
     * 返回值说明：无
     */
    handleStartScan(fullScan = false) {
        State.scanTaskType = 'scan';
        API.startScan(fullScan,
            () => {
                Toast.show(I18nManager.t('file_repo.scan_started'));
                UIController.toggleScanUI(true);
                UIController.showScanProgress();
                this.startScanPolling();
            },
            (msg) => {
                State.scanTaskType = '';
                Toast.show(msg);
            }
        );
    },

    /**
     * 用途说明：调用接口停止正在进行的索引扫描任务。
     * 入参说明：无
     * 返回值说明：无
     */
    handleStopScan() {
        API.stopScan(
            () => Toast.show(I18nManager.t('file_repo.stop_cmd_sent')),
            (msg) => Toast.show(msg)
        );
    },

    /**
     * 用途说明：启动扫描进度的实时轮询，完成后刷新相册列表。
     * 入参说明：无
     * 返回值说明：无
     */
    startScanPolling() {
        if (State.scanInterval) clearInterval(State.scanInterval);
        State.scanInterval = setInterval(() => {
            API.getScanProgress(
                (data) => {
                    if (data.status === ProgressStatus.PROCESSING) {
                        UIComponents.renderProgress('#album-main-content', data.progress);
                    } else {
                        /** @type {string} */
                        const taskType = State.scanTaskType;
                        this.stopScanPolling();
                        UIController.toggleScanUI(false);
                        if (data.status === ProgressStatus.COMPLETED) {
                            Toast.show(I18nManager.t(
                                taskType === 'metadata' ? 'file_repo.metadata_refresh_finished' : 'file_repo.scan_finished'
                            ));
                            this.loadFirstPage();
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
     * 用途说明：停止扫描进度轮询并隐藏进度遮罩。
     * 入参说明：无
     * 返回值说明：无
     */
    stopScanPolling() {
        if (State.scanInterval) {
            clearInterval(State.scanInterval);
            State.scanInterval = null;
        }
        State.scanTaskType = '';
        UIComponents.hideProgressBar('#album-main-content');
    },

    /**
     * 用途说明：页面初始化时检查是否已有正在运行的扫描任务，若有则恢复进度展示。
     * 入参说明：无
     * 返回值说明：无
     */
    checkScanStatus() {
        API.getScanProgress(
            (data) => {
                if (data.status === ProgressStatus.PROCESSING) {
                    State.scanTaskType = 'scan';
                    UIController.toggleScanUI(true);
                    UIController.showScanProgress();
                    this.startScanPolling();
                }
            },
            () => {}
        );
    },

    /**
     * 用途说明：绑定多选操作栏按钮事件。
     * 入参说明：无
     * 返回值说明：无
     */
    bindToolbarActions() {
        const { downloadSelectedBtn, deleteSelectedBtn, cancelSelectionBtn } = UIController.elements;
        if (downloadSelectedBtn) {
            downloadSelectedBtn.onclick = () => this.downloadFiles(Array.from(State.selected));
        }
        if (deleteSelectedBtn) {
            deleteSelectedBtn.onclick = () => this.deleteFiles(Array.from(State.selected), false);
        }
        if (cancelSelectionBtn) {
            cancelSelectionBtn.onclick = () => this.clearSelection();
        }
    },

    /**
     * 用途说明：处理搜索回调，重置分页后按关键词加载。
     * 入参说明：content (string) - 搜索关键词。
     * 返回值说明：无
     */
    handleSearch(content) {
        State.search = content || '';
        this.loadFirstPage();
    },

    /**
     * 用途说明：加载第一页数据（搜索/初始化时调用）。
     * 入参说明：无
     * 返回值说明：无
     */
    loadFirstPage() {
        State.page = 1;
        State.items = [];
        State.total = 0;
        State.hasMore = true;
        State.loading = false;
        State.queryToken++;
        State.ensureRequested.clear();
        State.ensureQueue = [];
        State.selected.clear();
        this.clearSelection();
        UIController.clearList();
        UIController.updateEmptyState();
        this.loadPage(1, true);
    },

    /**
     * 用途说明：加载下一页数据（无限滚动触发）。
     * 入参说明：无
     * 返回值说明：无
     */
    loadNextPage() {
        if (State.loading || !State.hasMore) return;
        this.loadPage(State.page + 1, false);
    },

    /**
     * 用途说明：执行分页请求并渲染结果。
     * 入参说明：
     *   page (number) - 页码。
     *   isFirst (boolean) - 是否为首屏（首屏失败时不显示"没有更多"）。
     * 返回值说明：无
     */
    loadPage(page, isFirst) {
        State.loading = true;
        if (UIController.elements.endTip) UIController.elements.endTip.classList.add('hidden');
        const token = State.queryToken;

        API.fetchList(page, (data) => {
            if (token !== State.queryToken) return;
            const list = (data && data.list) || [];
            State.page = (data && data.page) || page;
            State.total = (data && data.total) || 0;
            State.items = State.items.concat(list);
            State.hasMore = State.items.length < State.total;
            State.loading = false;

            UIController.appendItems(list);
            UIController.updateEmptyState();
            this.maybeLoadMore();
        }, (msg) => {
            if (token !== State.queryToken) return;
            State.loading = false;
            State.hasMore = false;
            Toast.show(msg || I18nManager.t('album.load_failed'));
            if (isFirst) UIController.updateEmptyState();
        });
    },

    /**
     * 用途说明：当首屏内容不足或哨兵仍在视口内时继续加载，避免无限滚动停住。
     * 入参说明：无
     * 返回值说明：无
     */
    maybeLoadMore() {
        if (!State.hasMore || State.loading) return;
        const sentinel = UIController.elements.sentinel;
        if (!sentinel) return;
        const rect = sentinel.getBoundingClientRect();
        if (rect.top < window.innerHeight + 200) {
            this.loadNextPage();
        }
    },

    /**
     * 用途说明：删除后重新拉取当前页，仅追加未见过的数据，补齐分页偏移产生的空缺。
     * 入参说明：无
     * 返回值说明：无
     */
    refillCurrentPage() {
        const token = State.queryToken;
        API.fetchList(State.page, (data) => {
            if (token !== State.queryToken) return;
            const existing = new Set(State.items.map(item => item.file_path));
            const list = ((data && data.list) || []).filter(item => !existing.has(item.file_path));
            State.total = (data && data.total) || State.total;
            State.items = State.items.concat(list);
            State.hasMore = State.items.length < State.total;
            UIController.appendItems(list);
            UIController.updateEmptyState();
            this.maybeLoadMore();
        }, (msg) => {
            console.error('Refill album page failed:', msg);
        });
    },

    /**
     * 用途说明：切换单个文件的选中状态。
     * 入参说明：filePath (string) - 媒体路径；selected (boolean) - 是否选中。
     * 返回值说明：无
     */
    toggleSelection(filePath, selected) {
        if (selected) State.selected.add(filePath);
        else State.selected.delete(filePath);
        UIController.setCardSelected(filePath, selected);
        UIController.updateSelectionBar();
    },

    /**
     * 用途说明：清空所有选中项。
     * 入参说明：无
     * 返回值说明：无
     */
    clearSelection() {
        const paths = Array.from(State.selected);
        State.selected.clear();
        paths.forEach(filePath => UIController.setCardSelected(filePath, false));
        UIController.updateSelectionBar();
    },

    /**
     * 用途说明：将缩略图生成任务加入并发队列。
     * 入参说明：filePath (string) - 媒体路径。
     * 返回值说明：无
     */
    enqueueThumbnail(filePath) {
        if (!filePath || State.ensureRequested.has(filePath)) return;
        State.ensureRequested.add(filePath);
        State.ensureQueue.push(filePath);
        this.pumpThumbnailQueue();
    },

    /**
     * 用途说明：按最大并发数消费缩略图生成队列。
     * 入参说明：无
     * 返回值说明：无
     */
    pumpThumbnailQueue() {
        while (State.ensureActive < State.ensureMax && State.ensureQueue.length > 0) {
            const filePath = State.ensureQueue.shift();
            State.ensureActive++;
            API.ensureThumbnail(filePath, (data) => {
                State.ensureActive--;
                if (data && data.thumbnail_path) {
                    UIController.applyThumbnail(filePath, data.thumbnail_path);
                } else {
                    UIController.markThumbnailFailed(filePath);
                }
                this.pumpThumbnailQueue();
            }, () => {
                State.ensureActive--;
                UIController.markThumbnailFailed(filePath);
                this.pumpThumbnailQueue();
            });
        }
    },

    /**
     * 用途说明：下载指定文件（单项立即下载，多项按顺序依次触发）。
     * 入参说明：filePaths (Array<string>) - 文件路径列表。
     * 返回值说明：无
     */
    downloadFiles(filePaths) {
        if (!filePaths || filePaths.length === 0) return;
        filePaths.forEach((filePath, index) => {
            setTimeout(() => {
                const anchor = document.createElement('a');
                anchor.href = AlbumBrowseRequest.buildDownloadUrl(filePath);
                anchor.download = '';
                document.body.appendChild(anchor);
                anchor.click();
                document.body.removeChild(anchor);
            }, index * 300);
        });
    },

    /**
     * 用途说明：删除（移入回收站）指定文件，执行前二次确认。
     * 入参说明：
     *   filePaths (Array<string>) - 文件路径列表。
     *   fromPreview (boolean) - 是否来自预览弹窗（删除后关闭预览）。
     * 返回值说明：无
     */
    deleteFiles(filePaths, fromPreview) {
        if (State.repoPermission !== 'admin') return;
        if (!filePaths || filePaths.length === 0) return;
        const message = filePaths.length > 1
            ? I18nManager.t('album.delete_confirm_msg', { count: filePaths.length })
            : I18nManager.t('album.delete_single_confirm_msg');

        UIComponents.showConfirmModal({
            title: I18nManager.t('album.delete_confirm_title'),
            message: message,
            confirmText: I18nManager.t('common.confirm'),
            onConfirm: () => {
                API.deleteFiles(filePaths, () => {
                    State.items = State.items.filter(item => !filePaths.includes(item.file_path));
                    State.total = Math.max(0, State.total - filePaths.length);
                    UIController.removeByPaths(filePaths);
                    UIController.updateSelectionBar();
                    if (fromPreview) {
                        UIController.closePreview();
                    }
                    Toast.show(I18nManager.t('album.delete_success'));
                    // 删除后重新拉取当前页，补齐因位置前移产生的空缺，避免翻页漏图
                    if (State.hasMore) this.refillCurrentPage();
                }, (msg) => {
                    Toast.show(msg || I18nManager.t('album.delete_failed'));
                });
            }
        });
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());