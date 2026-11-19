/**
 * @description 文件整理页面逻辑：逐个展示待整理文件，预览、改名并保存到已整理目录，
 *              左侧待整理列表默认折叠、可展开与拖动调宽，全部完成后弹出庆祝弹窗。
 */

// --- 状态管理 ---
const State = {
    total: 0, // 本次任务扫描到的文件总数
    remaining: 0, // 剩余待整理文件数
    page: 1, // 侧栏列表当前页码
    pageSize: 50, // 侧栏列表每页条数
    items: [], // 当前页的待整理文件条目
    current: null, // 当前正在整理的文件条目
    saving: false, // 是否正在保存（防重复提交）
    sidebarCollapsed: true, // 侧栏是否折叠（默认折叠）
    sidebarWidth: 280 // 侧栏宽度（像素，拖动后持久化）
};

// 侧栏偏好本地存储键
const SIDEBAR_COLLAPSED_KEY = 'organizeTask.sidebarCollapsed';
const SIDEBAR_WIDTH_KEY = 'organizeTask.sidebarWidth';
// 侧栏拖动宽度范围（像素）
const SIDEBAR_MIN_WIDTH = 200;
const SIDEBAR_MAX_WIDTH = 480;

// --- UI 控制模块 ---
const UIController = {
    elements: {},

    /**
     * @description 用途说明：初始化页面 UI，渲染多语言并初始化顶部栏（返回主页，右上角进入整理设置）。
     * @returns {void} - 返回值说明：无
     */
    init() {
        I18nManager.init();
        I18nManager.render();

        HeaderToolbar.init({
            title: I18nManager.t('organize.task.title'),
            showBack: true,
            backCallback: () => { window.location.href = '../home/home.html'; },
            menuIcon: '../common/header_toolbar/icon/settings_icon.svg',
            menuCallback: () => { window.location.href = 'organize_setting.html'; }
        });

        this.elements = {
            layout: document.getElementById('task-layout'),
            sidebar: document.getElementById('task-sidebar'),
            sidebarList: document.getElementById('sidebar-list'),
            sidebarCount: document.getElementById('sidebar-count'),
            resizer: document.getElementById('sidebar-resizer'),
            scrim: document.getElementById('sidebar-scrim'),
            toggle: document.getElementById('sidebar-toggle'),
            stateLoading: document.getElementById('state-loading'),
            stateNoconfig: document.getElementById('state-noconfig'),
            stateEmpty: document.getElementById('state-empty'),
            workArea: document.getElementById('work-area'),
            statRemaining: document.getElementById('stat-remaining'),
            statProgress: document.getElementById('stat-progress'),
            progressFill: document.getElementById('progress-fill'),
            previewBox: document.getElementById('preview-box'),
            originalName: document.getElementById('original-name'),
            newNameInput: document.getElementById('new-name-input'),
            saveBtn: document.getElementById('save-btn'),
            skipBtn: document.getElementById('skip-btn'),
            recycleBtn: document.getElementById('recycle-btn'),
            completeModal: document.getElementById('complete-modal'),
            completeMsg: document.getElementById('complete-msg'),
            completeStat: document.getElementById('complete-stat')
        };
    },

    /**
     * @description 用途说明：切换页面主状态视图（扫描中 / 未配置 / 空列表 / 工作区）。
     * @param {string} name - 入参说明：状态名 loading | noconfig | empty | work。
     * @returns {void} - 返回值说明：无
     */
    showState(name) {
        const map = {
            loading: this.elements.stateLoading,
            noconfig: this.elements.stateNoconfig,
            empty: this.elements.stateEmpty,
            work: this.elements.workArea
        };
        Object.keys(map).forEach(key => {
            map[key].classList.toggle('hidden', key !== name);
        });
    },

    /**
     * @description 用途说明：刷新剩余数量、整理进度文案与进度条。
     * @returns {void} - 返回值说明：无
     */
    renderStats() {
        const done = Math.max(0, State.total - State.remaining);
        this.elements.statRemaining.textContent = String(State.remaining);
        this.elements.statProgress.textContent = I18nManager.t('organize.task.progress_text', {
            done: done, total: State.total
        });
        const percent = State.total > 0 ? Math.round(done / State.total * 100) : 0;
        this.elements.progressFill.style.width = percent + '%';
        this.elements.sidebarCount.textContent = String(State.remaining);
    },

    /**
     * @description 用途说明：渲染侧栏待整理文件列表与分页栏，并高亮当前条目。
     * @returns {void} - 返回值说明：无
     */
    renderSidebar() {
        const list = this.elements.sidebarList;
        list.innerHTML = '';
        State.items.forEach(item => {
            const row = document.createElement('div');
            row.className = 'sidebar-item' + (State.current && State.current.path === item.path ? ' active' : '');
            row.title = item.path;

            const typeIcon = document.createElement('span');
            typeIcon.className = 'item-type type-' + item.file_type;
            row.appendChild(typeIcon);

            const nameEl = document.createElement('span');
            nameEl.className = 'item-name';
            nameEl.textContent = item.name;
            row.appendChild(nameEl);

            const sizeEl = document.createElement('span');
            sizeEl.className = 'item-size';
            sizeEl.textContent = CommonUtils.formatFileSize(item.size);
            row.appendChild(sizeEl);

            row.onclick = () => App.selectItem(item);
            list.appendChild(row);
        });

        PageBar.init({
            containerId: 'sidebar-page-bar',
            totalItems: State.remaining,
            pageSize: State.pageSize,
            currentPage: State.page,
            onPageChange: (page) => App.loadPending(page, true)
        });
    },

    /**
     * @description 用途说明：渲染当前文件的预览框（图片 / 视频 / 其他类型占位）。
     * @param {Object} item - 入参说明：待整理文件条目 {path, name, file_type, size, suggestion}。
     * @returns {void} - 返回值说明：无
     */
    renderPreview(item) {
        const box = this.elements.previewBox;
        box.innerHTML = '';
        const url = OrganizeTaskRequest.buildPreviewUrl(item.path);

        if (item.file_type === 'image') {
            const img = document.createElement('img');
            img.className = 'preview-media';
            img.alt = item.name;
            img.onerror = () => this.renderPreviewPlaceholder('organize.task.preview_failed');
            img.src = url;
            box.appendChild(img);
        } else if (item.file_type === 'video') {
            const video = document.createElement('video');
            video.className = 'preview-media';
            video.controls = true;
            video.preload = 'metadata';
            video.playsInline = true;
            video.onerror = () => this.renderPreviewPlaceholder('organize.task.preview_failed');
            video.src = url;
            box.appendChild(video);
        } else {
            this.renderPreviewPlaceholder('organize.task.preview_unsupported');
        }
    },

    /**
     * @description 用途说明：在预览框内渲染占位提示（不支持预览或加载失败）。
     * @param {string} textKey - 入参说明：提示文案的多语言 Key。
     * @returns {void} - 返回值说明：无
     */
    renderPreviewPlaceholder(textKey) {
        const box = this.elements.previewBox;
        box.innerHTML = '';
        const wrap = document.createElement('div');
        wrap.className = 'preview-placeholder';
        const icon = document.createElement('div');
        icon.className = 'placeholder-icon';
        const text = document.createElement('p');
        text.className = 'placeholder-text';
        text.textContent = I18nManager.t(textKey);
        wrap.appendChild(icon);
        wrap.appendChild(text);
        box.appendChild(wrap);
    },

    /**
     * @description 用途说明：渲染当前文件的原文件名与建议文件名输入框（输入框仅展示不含后缀的文件名主体）。
     * @param {Object} item - 入参说明：待整理文件条目 {path, name, file_type, size, suggestion}。
     * @returns {void} - 返回值说明：无
     */
    renderCurrent(item) {
        this.elements.originalName.textContent = item.name;
        this.elements.originalName.title = item.path;
        // 建议文件名来自整理脚本（含后缀），输入框去掉最后一级后缀，后缀由后端保存时自动保留
        this.elements.newNameInput.value = this.stripExtension(item.suggestion || item.name);
        this.renderPreview(item);
    },

    /**
     * @description 用途说明：去掉文件名最后一级后缀（与后端 splitext 行为一致）；无后缀或以点开头的隐藏名原样返回。
     * @param {string} name - 入参说明：含后缀的文件名（不含路径）。
     * @returns {string} - 返回值说明：不含最后一级后缀的文件名主体。
     */
    stripExtension(name) {
        const base = String(name || '');
        const idx = base.lastIndexOf('.');
        if (idx <= 0) return base;
        return base.slice(0, idx);
    },

    /**
     * @description 用途说明：应用侧栏折叠/展开状态（宽度、拖动条、移动端遮罩与切换按钮提示）。
     * @returns {void} - 返回值说明：无
     */
    applySidebar() {
        const collapsed = State.sidebarCollapsed;
        const mobile = window.matchMedia('(max-width: 720px)').matches;
        this.elements.sidebar.classList.toggle('collapsed', collapsed);
        this.elements.toggle.classList.toggle('is-open', !collapsed);
        this.elements.toggle.title = I18nManager.t(collapsed ? 'organize.task.sidebar_open' : 'organize.task.sidebar_collapse');
        // 拖动条仅桌面端展开时可用；移动端用遮罩点击收起
        this.elements.resizer.classList.toggle('hidden', collapsed || mobile);
        this.elements.scrim.classList.toggle('hidden', collapsed || !mobile);
        if (!collapsed && !mobile) {
            this.elements.sidebar.style.width = State.sidebarWidth + 'px';
        } else {
            this.elements.sidebar.style.width = '';
        }
    },

    /**
     * @description 用途说明：设置操作忙碌状态（保存 / 跳过 / 删除共用，防重复提交并给出视觉反馈）。
     * @param {boolean} saving - 入参说明：是否正在执行操作。
     * @returns {void} - 返回值说明：无
     */
    setSaving(saving) {
        State.saving = saving;
        this.elements.saveBtn.disabled = saving;
        this.elements.saveBtn.classList.toggle('is-saving', saving);
        this.elements.skipBtn.disabled = saving;
        this.elements.recycleBtn.disabled = saving;
    },

    /**
     * @description 用途说明：弹出整理完成庆祝弹窗，随机展示一条成就文案与本次整理数量。
     * @returns {void} - 返回值说明：无
     */
    showComplete() {
        const index = 1 + Math.floor(Math.random() * 6);
        this.elements.completeMsg.textContent = I18nManager.t('organize.task.complete_msg_' + index);
        this.elements.completeStat.textContent = I18nManager.t('organize.task.complete_stat', { count: State.total });
        this.elements.completeModal.classList.remove('hidden');
    },

    /**
     * @description 用途说明：关闭整理完成庆祝弹窗。
     * @returns {void} - 返回值说明：无
     */
    hideComplete() {
        this.elements.completeModal.classList.add('hidden');
    }
};

// --- 应用逻辑主入口 ---
const App = {
    /**
     * @description 用途说明：初始化应用，恢复侧栏偏好、绑定事件并检查配置后启动整理任务。
     * @returns {void} - 返回值说明：无
     */
    init() {
        UIController.init();
        this.restoreSidebarPrefs();
        UIController.applySidebar();
        this.bindEvents();
        this.checkSettingsThenStart();
    },

    /**
     * @description 用途说明：从本地存储恢复侧栏折叠状态与宽度偏好。
     * @returns {void} - 返回值说明：无
     */
    restoreSidebarPrefs() {
        const collapsed = localStorage.getItem(SIDEBAR_COLLAPSED_KEY);
        // 默认折叠：仅当明确保存过展开状态时才展开
        State.sidebarCollapsed = collapsed !== '0';
        const width = parseInt(localStorage.getItem(SIDEBAR_WIDTH_KEY), 10);
        if (!isNaN(width)) {
            State.sidebarWidth = Math.min(SIDEBAR_MAX_WIDTH, Math.max(SIDEBAR_MIN_WIDTH, width));
        }
    },

    /**
     * @description 用途说明：绑定页面全部交互事件（侧栏开关/拖动、保存、复制、重扫、弹窗等）。
     * @returns {void} - 返回值说明：无
     */
    bindEvents() {
        const el = UIController.elements;

        el.toggle.onclick = () => {
            State.sidebarCollapsed = !State.sidebarCollapsed;
            localStorage.setItem(SIDEBAR_COLLAPSED_KEY, State.sidebarCollapsed ? '1' : '0');
            UIController.applySidebar();
        };
        el.scrim.onclick = () => {
            State.sidebarCollapsed = true;
            localStorage.setItem(SIDEBAR_COLLAPSED_KEY, '1');
            UIController.applySidebar();
        };

        // 侧栏宽度拖动（Pointer 事件兼容鼠标与触屏）
        el.resizer.addEventListener('pointerdown', (e) => {
            e.preventDefault();
            el.resizer.setPointerCapture(e.pointerId);
            document.body.classList.add('sidebar-dragging');
            const layoutLeft = el.layout.getBoundingClientRect().left;
            const onMove = (ev) => {
                const width = Math.min(SIDEBAR_MAX_WIDTH, Math.max(SIDEBAR_MIN_WIDTH, ev.clientX - layoutLeft));
                State.sidebarWidth = width;
                el.sidebar.style.width = width + 'px';
            };
            const onUp = () => {
                document.body.classList.remove('sidebar-dragging');
                localStorage.setItem(SIDEBAR_WIDTH_KEY, String(State.sidebarWidth));
                el.resizer.removeEventListener('pointermove', onMove);
                el.resizer.removeEventListener('pointerup', onUp);
                el.resizer.removeEventListener('pointercancel', onUp);
            };
            el.resizer.addEventListener('pointermove', onMove);
            el.resizer.addEventListener('pointerup', onUp);
            el.resizer.addEventListener('pointercancel', onUp);
        });

        // 窗口尺寸变化时重新应用侧栏布局（桌面/移动断点切换）
        window.addEventListener('resize', () => UIController.applySidebar());

        document.getElementById('rescan-btn').onclick = () => this.startTask();
        document.getElementById('empty-rescan-btn').onclick = () => this.startTask();
        document.getElementById('noconfig-setting-btn').onclick = () => { window.location.href = 'organize_setting.html'; };
        document.getElementById('empty-setting-btn').onclick = () => { window.location.href = 'organize_setting.html'; };

        document.getElementById('copy-name-btn').onclick = () => this.copyOriginalName();
        el.saveBtn.onclick = () => this.handleSave();
        el.skipBtn.onclick = () => this.handleSkip();
        el.recycleBtn.onclick = () => this.handleRecycle();
        el.newNameInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.handleSave();
            }
        });

        document.getElementById('complete-close-btn').onclick = () => UIController.hideComplete();
        document.getElementById('complete-again-btn').onclick = () => {
            UIController.hideComplete();
            this.startTask();
        };
    },

    /**
     * @description 用途说明：先读取整理设置判断目录是否已配置，未配置展示引导视图，已配置则启动任务。
     * @returns {void} - 返回值说明：无
     */
    checkSettingsThenStart() {
        UIController.showState('loading');
        OrganizeTaskRequest.getSettings(
            (settings) => {
                const dirs = (settings && settings.pending_dirs) || [];
                const target = (settings && settings.organized_dir) || '';
                if (dirs.length === 0 || !target) {
                    UIController.showState('noconfig');
                    return;
                }
                this.startTask();
            },
            (msg) => {
                Toast.show(I18nManager.t('organize.task.start_failed') + ': ' + msg);
                UIController.showState('noconfig');
            }
        );
    },

    /**
     * @description 用途说明：启动整理任务（后端重新扫描待整理目录），成功后加载第一页并选中首个文件。
     * @returns {void} - 返回值说明：无
     */
    startTask() {
        UIController.showState('loading');
        OrganizeTaskRequest.startTask(
            (data) => {
                State.total = data.total;
                State.remaining = data.remaining;
                State.current = null;
                if (State.remaining === 0) {
                    UIController.renderStats();
                    UIController.showState('empty');
                    return;
                }
                this.loadPending(1, true);
            },
            (msg) => {
                Toast.show(I18nManager.t('organize.task.start_failed') + ': ' + msg);
                UIController.showState('noconfig');
            }
        );
    },

    /**
     * @description 用途说明：分页加载剩余待整理文件并渲染侧栏；按需自动选中当前页首个文件。
     * @param {number} page - 入参说明：目标页码（从 1 开始）。
     * @param {boolean} selectFirst - 入参说明：加载后是否选中本页首个文件。
     * @param {boolean} [focusInput=false] - 入参说明：选中后是否聚焦文件名输入框（桌面端保存后连续整理）。
     * @returns {void} - 返回值说明：无
     */
    loadPending(page, selectFirst, focusInput) {
        OrganizeTaskRequest.getPending(page, State.pageSize,
            (data) => {
                State.total = data.total;
                State.remaining = data.remaining;
                State.page = data.page;
                State.items = data.items || [];
                UIController.renderStats();

                // 保存后当前页可能已超出范围：回退到最后一个有效页
                if (State.items.length === 0 && State.remaining > 0 && State.page > 1) {
                    this.loadPending(State.page - 1, selectFirst, focusInput);
                    return;
                }
                if (State.remaining === 0) {
                    UIController.showState('empty');
                    UIController.renderSidebar();
                    return;
                }

                UIController.showState('work');
                const stillHere = State.current && State.items.some(it => it.path === State.current.path);
                if (selectFirst || !stillHere) {
                    this.selectItem(State.items[0], focusInput);
                } else {
                    UIController.renderSidebar();
                }
            },
            (msg) => {
                Toast.show(I18nManager.t('organize.task.load_failed') + ': ' + msg);
            }
        );
    },

    /**
     * @description 用途说明：选中一个待整理文件作为当前整理对象，渲染预览与文件名输入。
     * @param {Object} item - 入参说明：待整理文件条目 {path, name, file_type, size, suggestion}。
     * @param {boolean} [focusInput=false] - 入参说明：是否聚焦文件名输入框（仅桌面端生效，避免移动端弹键盘）。
     * @returns {void} - 返回值说明：无
     */
    selectItem(item, focusInput) {
        if (!item) return;
        State.current = item;
        UIController.renderCurrent(item);
        UIController.renderSidebar();
        if (focusInput && !window.matchMedia('(max-width: 720px)').matches) {
            UIController.elements.newNameInput.focus();
            UIController.elements.newNameInput.select();
        }
    },

    /**
     * @description 用途说明：保存当前整理结果：校验文件名主体（不含后缀）后请求后端改名移动，成功后推进到下一个文件。
     * @returns {void} - 返回值说明：无
     */
    handleSave() {
        if (State.saving || !State.current) return;
        // 输入为不含后缀的文件名主体；后端保存时自动拼接原文件后缀（误带后缀时后端会去重）
        const newName = UIController.elements.newNameInput.value.trim();
        if (!newName) {
            Toast.show(I18nManager.t('organize.task.name_required'));
            return;
        }
        UIController.setSaving(true);
        OrganizeTaskRequest.saveFile(State.current.path, newName,
            (data) => {
                UIController.setSaving(false);
                Toast.show(I18nManager.t('organize.task.save_success'));
                this.advance(data);
            },
            (msg) => {
                UIController.setSaving(false);
                Toast.show(I18nManager.t('common.error') + ': ' + msg);
            }
        );
    },

    /**
     * @description 用途说明：跳过当前文件：仅移出本次任务队列（不动文件），成功后推进到下一个文件。
     * @returns {void} - 返回值说明：无
     */
    handleSkip() {
        if (State.saving || !State.current) return;
        UIController.setSaving(true);
        OrganizeTaskRequest.skipFile(State.current.path,
            (data) => {
                UIController.setSaving(false);
                Toast.show(I18nManager.t('organize.task.skip_success'));
                this.advance(data);
            },
            (msg) => {
                UIController.setSaving(false);
                Toast.show(I18nManager.t('organize.task.skip_failed') + ': ' + msg);
            }
        );
    },

    /**
     * @description 用途说明：删除当前文件（二次确认后移入回收站，可在回收站恢复）。
     * @returns {void} - 返回值说明：无
     */
    handleRecycle() {
        if (State.saving || !State.current) return;
        const item = State.current;
        UIComponents.showConfirmModal({
            title: I18nManager.t('organize.task.recycle_title'),
            message: I18nManager.t('organize.task.recycle_message', { name: item.name }),
            confirmText: I18nManager.t('organize.task.recycle'),
            onConfirm: () => this.requestRecycle(item.path)
        });
    },

    /**
     * @description 用途说明：调用后端把文件移入回收站，成功后推进到下一个文件。
     * @param {string} path - 入参说明：待删除（移入回收站）的文件完整路径。
     * @returns {void} - 返回值说明：无
     */
    requestRecycle(path) {
        UIController.setSaving(true);
        OrganizeTaskRequest.recycleFile(path,
            (data) => {
                UIController.setSaving(false);
                Toast.show(I18nManager.t('organize.task.recycle_success'));
                this.advance(data);
            },
            (msg) => {
                UIController.setSaving(false);
                Toast.show(I18nManager.t('organize.task.recycle_failed') + ': ' + msg);
            }
        );
    },

    /**
     * @description 用途说明：处理后推进：刷新进度，全部处理完弹出完成弹窗，否则选中下一个文件并回退越界页码。
     * @param {Object} data - 入参说明：后端返回的 {remaining, total}。
     * @returns {void} - 返回值说明：无
     */
    advance(data) {
        State.remaining = data.remaining;
        State.total = data.total;
        State.current = null;
        UIController.renderStats();
        if (State.remaining === 0) {
            UIController.showState('empty');
            UIController.renderSidebar();
            UIController.showComplete();
            return;
        }
        // 处理后停留在当前页（超界自动回退），选中下一个文件并聚焦输入框
        const maxPage = Math.max(1, Math.ceil(State.remaining / State.pageSize));
        this.loadPending(Math.min(State.page, maxPage), true, true);
    },

    /**
     * @description 用途说明：复制当前文件的原文件名到剪贴板（优先异步剪贴板 API，失败回退隐藏文本域）。
     * @returns {void} - 返回值说明：无
     */
    copyOriginalName() {
        if (!State.current) return;
        const text = State.current.name;
        const fallback = () => {
            const textarea = document.createElement('textarea');
            textarea.value = text;
            textarea.className = 'copy-fallback-textarea';
            document.body.appendChild(textarea);
            textarea.select();
            let ok = false;
            try {
                ok = document.execCommand('copy');
            } catch (e) {
                ok = false;
            }
            document.body.removeChild(textarea);
            Toast.show(I18nManager.t(ok ? 'organize.task.copied' : 'organize.task.copy_failed'));
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text)
                .then(() => Toast.show(I18nManager.t('organize.task.copied')))
                .catch(fallback);
        } else {
            fallback();
        }
    }
};

// 页面加载完成后启动
document.addEventListener('DOMContentLoaded', () => App.init());