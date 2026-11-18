/**
 * @description 整理设置页面逻辑处理，负责待整理目录、已整理目录与后缀名输入框的编辑及保存。
 */

// --- 状态管理 ---
const State = {
    pendingDirs: [], // 待整理目录列表
    organizedDir: '', // 已整理目录路径
    extensions: [] // 需要整理的后缀名列表
};

// --- UI 控制模块 ---
const UIController = {
    elements: {},

    /**
     * @description 用途说明：初始化页面 UI，渲染多语言并初始化顶部栏（右上角为保存按钮）。
     * @returns {void} - 返回值说明：无
     */
    init() {
        I18nManager.init();
        I18nManager.render();

        HeaderToolbar.init({
            title: I18nManager.t('organize.setting.title'),
            showBack: true,
            menuIcon: '../common/header_toolbar/icon/save_icon.svg',
            menuCallback: () => App.handleSave()
        });

        this.elements = {
            pendingDirList: document.getElementById('pending-dir-list'),
            extensionsInput: document.getElementById('extensions-input'),
            organizedDirInput: document.getElementById('organized-dir-input')
        };
    },

    /**
     * @description 用途说明：将后端返回的设置数据填充到页面状态与表单。
     * @param {Object} data - 入参说明：设置数据对象 {pending_dirs, organized_dir, extensions}。
     * @returns {void} - 返回值说明：无
     */
    fillForm(data) {
        State.pendingDirs = (data && data.pending_dirs) || [];
        State.organizedDir = (data && data.organized_dir) || '';
        State.extensions = (data && data.extensions) || [];
        this.elements.organizedDirInput.value = State.organizedDir;
        this.elements.extensionsInput.value = State.extensions.join(', ');
        this.renderPendingDirs();
    },

    /**
     * @description 用途说明：渲染待整理目录列表。
     * @returns {void} - 返回值说明：无
     */
    renderPendingDirs() {
        this.renderList(this.elements.pendingDirList, State.pendingDirs, (index) => App.handleDeletePendingDir(index));
    },

    /**
     * @description 用途说明：通用列表渲染，为每个条目生成文本与移除按钮，空列表时展示占位提示。
     * @param {HTMLElement} container - 入参说明：列表容器 DOM 元素。
     * @param {string[]} items - 入参说明：待渲染的文本条目数组。
     * @param {Function} onDelete - 入参说明：移除回调，参数为条目索引。
     * @returns {void} - 返回值说明：无
     */
    renderList(container, items, onDelete) {
        if (!container) return;
        container.innerHTML = '';

        if (!items || items.length === 0) {
            const empty = document.createElement('div');
            empty.className = 'empty-hint-text';
            empty.textContent = I18nManager.t('common.no_data');
            container.appendChild(empty);
            return;
        }

        items.forEach((text, index) => {
            const item = document.createElement('div');
            item.className = 'organize-item';

            const textEl = document.createElement('div');
            textEl.className = 'organize-item-text';
            textEl.textContent = text;

            const actions = document.createElement('div');
            actions.className = 'organize-item-actions';
            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'btn-delete';
            deleteBtn.textContent = I18nManager.t('common.delete');
            deleteBtn.onclick = () => onDelete(index);
            actions.appendChild(deleteBtn);

            item.appendChild(textEl);
            item.appendChild(actions);
            container.appendChild(item);
        });
    }
};

// --- 应用逻辑主入口 ---
const App = {
    /**
     * @description 用途说明：初始化应用，绑定事件并加载整理设置。
     * @returns {void} - 返回值说明：无
     */
    init() {
        UIController.init();
        this.bindEvents();
        this.loadSettings();
    },

    /**
     * @description 用途说明：绑定页面交互事件（待整理目录添加按钮）。
     * @returns {void} - 返回值说明：无
     */
    bindEvents() {
        document.getElementById('add-pending-dir-btn').onclick = () => this.handleAddPendingDir();
    },

    /**
     * @description 用途说明：从后端异步加载当前仓库的整理设置并触发 UI 渲染。
     * @returns {void} - 返回值说明：无
     */
    loadSettings() {
        OrganizeSettingRequest.getSettings(
            (data) => {
                UIController.fillForm(data);
            },
            (msg) => {
                Toast.show(I18nManager.t('common.error') + ': ' + msg);
            }
        );
    },

    /**
     * @description 用途说明：弹窗输入并添加新的待整理目录（去空白、查重后加入本地状态）。
     * @returns {void} - 返回值说明：无
     */
    handleAddPendingDir() {
        UIComponents.showInputModal({
            title: I18nManager.t('organize.setting.add_dir'),
            placeholder: I18nManager.t('organize.setting.add_dir_placeholder'),
            onConfirm: (value) => {
                const path = (value || '').trim();
                if (!path) {
                    Toast.show(I18nManager.t('common.input_path'));
                    return;
                }
                if (State.pendingDirs.includes(path)) {
                    Toast.show(I18nManager.t('common.path_exists'));
                    return;
                }
                State.pendingDirs.push(path);
                UIController.renderPendingDirs();
            }
        });
    },

    /**
     * @description 用途说明：从本地状态中移除指定索引的待整理目录并重新渲染列表。
     * @param {number} index - 入参说明：待移除目录在数组中的索引。
     * @returns {void} - 返回值说明：无
     */
    handleDeletePendingDir(index) {
        State.pendingDirs.splice(index, 1);
        UIController.renderPendingDirs();
    },

    /**
     * @description 用途说明：采集页面数据并提交保存整理设置，成功后用后端归一化结果刷新页面。
     * @returns {void} - 返回值说明：无
     */
    handleSave() {
        // 解析后缀名输入框：按英文逗号分隔，去除首尾空白并过滤空项
        const extensions = UIController.elements.extensionsInput.value
            .split(',')
            .map(s => s.trim())
            .filter(s => s);
        // 后缀名不允许包含空白或路径分隔符，防止误录入路径
        if (extensions.some(ext => /\s/.test(ext) || ext.includes('/') || ext.includes('\\'))) {
            Toast.show(I18nManager.t('organize.setting.ext_invalid'));
            return;
        }

        const data = {
            pending_dirs: State.pendingDirs,
            organized_dir: UIController.elements.organizedDirInput.value.trim(),
            extensions: extensions
        };
        OrganizeSettingRequest.updateSettings(
            data,
            (saved) => {
                Toast.show(I18nManager.t('common.success'));
                UIController.fillForm(saved);
            },
            (msg) => {
                Toast.show(I18nManager.t('common.error') + ': ' + msg);
            }
        );
    }
};

// 页面加载完成后启动
document.addEventListener('DOMContentLoaded', () => App.init());