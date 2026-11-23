/**
 * 用途说明：相册浏览页面逻辑，负责瀑布流渲染、搜索、无限滚动、按需生成缩略图、
 * 单项/批量下载与删除（移入回收站），以及媒体预览弹窗（图片/视频切换、下载、删除）。
 * 模块划分：State（状态）、UIController（DOM 与渲染）、API（接口封装）、App（入口与事件绑定）。
 */

// --- 状态管理 ---
const State = {
    page: 1,
    limit: 30,
    search: '',
    sortBy: 'scan_time',
    orderAsc: false,
    items: [],
    total: 0,
    loading: false,
    hasMore: true,
    selected: new Set(), // 已选中的文件路径集合
    cardMap: new Map(), // file_path -> { card, item, img, placeholder, placeholderText }
    ensureRequested: new Set(), // 已发起缩略图生成请求的路径
    ensureQueue: [], // 缩略图生成待处理队列
    ensureActive: 0, // 当前进行中的缩略图请求数
    ensureMax: 3, // 缩略图请求最大并发数
    previewIndex: -1, // 当前预览索引，-1 表示未打开
    queryToken: 0, // 请求代次，用于丢弃搜索切换后的过期响应
    sentinelObserver: null,
    cardObserver: null
};

// --- API 封装 ---
const API = {
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
            searchCallback: (content) => App.handleSearch(content)
        });

        this.elements = {
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
            previewDownloadBtn: document.getElementById('album-preview-download'),
            previewDeleteBtn: document.getElementById('album-preview-delete'),
            previewCloseBtn: document.getElementById('album-preview-close'),
            previewPrevBtn: document.getElementById('album-preview-prev'),
            previewNextBtn: document.getElementById('album-preview-next')
        };

        this.initObservers();
        this.bindPreviewEvents();
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
        if (this.elements.previewDeleteBtn) {
            this.elements.previewDeleteBtn.onclick = () => {
                const item = State.items[State.previewIndex];
                if (item) App.deleteFiles([item.file_path], true);
            };
        }
        if (this.elements.previewMask) {
            this.elements.previewMask.addEventListener('click', (e) => {
                // 点击遮罩空白处（非媒体、非按钮）关闭预览
                if (e.target === this.elements.previewMask) this.closePreview();
            });
        }
        document.addEventListener('keydown', (e) => {
            if (State.previewIndex < 0) return;
            if (e.key === 'Escape') this.closePreview();
            else if (e.key === 'ArrowLeft') this.previewStep(-1);
            else if (e.key === 'ArrowRight') this.previewStep(1);
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
        placeholderIcon.className = 'album-placeholder-icon';
        placeholderIcon.textContent = item.file_type === 'video' ? '🎬' : '🖼️';
        const placeholderText = document.createElement('span');
        placeholderText.className = 'album-placeholder-text';
        placeholderText.textContent = I18nManager.t('album.thumbnail_generating');
        placeholder.appendChild(placeholderIcon);
        placeholder.appendChild(placeholderText);

        const img = document.createElement('img');
        img.className = 'album-thumb hidden';
        img.alt = item.file_name;
        img.loading = 'lazy';
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
        downloadBtn.textContent = '⬇';
        downloadBtn.onclick = (e) => {
            e.stopPropagation();
            App.downloadFiles([item.file_path]);
        };
        const deleteBtn = document.createElement('button');
        deleteBtn.type = 'button';
        deleteBtn.className = 'album-action-btn album-action-danger';
        deleteBtn.title = I18nManager.t('album.delete');
        deleteBtn.textContent = '🗑';
        deleteBtn.onclick = (e) => {
            e.stopPropagation();
            App.deleteFiles([item.file_path], false);
        };
        actions.appendChild(downloadBtn);
        actions.appendChild(deleteBtn);
        wrap.appendChild(actions);

        const name = document.createElement('div');
        name.className = 'album-name';
        name.textContent = item.file_name;

        card.appendChild(wrap);
        card.appendChild(name);
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
     * 用途说明：渲染一页媒体卡片并追加到瀑布流。
     * 入参说明：list (Array<Object>) - 媒体项数组。
     * 返回值说明：无
     */
    appendItems(list) {
        if (!this.elements.waterfall) return;
        const fragment = document.createDocumentFragment();
        list.forEach(item => fragment.appendChild(this.createCard(item)));
        this.elements.waterfall.appendChild(fragment);
    },

    /**
     * 用途说明：重置列表 DOM 与卡片缓存（用于搜索或首次加载）。
     * 入参说明：无
     * 返回值说明：无
     */
    clearList() {
        if (this.elements.waterfall) this.elements.waterfall.textContent = '';
        State.cardMap.clear();
    },

    /**
     * 用途说明：根据文件路径批量移除卡片并同步选中状态。
     * 入参说明：filePaths (Array<string>) - 待移除的文件路径列表。
     * 返回值说明：无
     */
    removeByPaths(filePaths) {
        filePaths.forEach(filePath => {
            const info = State.cardMap.get(filePath);
            if (info && info.card.parentNode) info.card.parentNode.removeChild(info.card);
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
        document.body.classList.add('album-preview-open');
        if (this.elements.previewName) this.elements.previewName.textContent = item.file_name;

        const body = this.elements.previewBody;
        if (body) {
            body.textContent = '';
            if (item.file_type === 'video') {
                const video = document.createElement('video');
                video.className = 'album-preview-media';
                video.controls = true;
                video.autoplay = true;
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
        this.loadFirstPage();
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