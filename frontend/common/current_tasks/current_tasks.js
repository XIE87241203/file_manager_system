/**
 * 用途说明：顶部“当前任务”按钮与下方弹出面板，聚合展示长任务进度并提供管理员控制入口。
 * 模块划分：State 管理任务和轮询；UIController 管理挂载与渲染；API 封装请求；App 管理生命周期。
 */
const CurrentTasksState = {
    tasks: [],
    open: false,
    loading: false,
    timer: null,
    controlling: '',
    initialized: false
};

const CurrentTasksAPI = {
    /**
     * 用途说明：读取任务列表。
     * 入参说明：onSuccess (Function) - 成功回调；onError (Function) - 失败回调。
     * 返回值说明：无。
     */
    list(onSuccess, onError) {
        CurrentTasksRequest.list(onSuccess, onError);
    },

    /**
     * 用途说明：控制指定任务。
     * 入参说明：task (Object) - 任务快照；action (string) - 操作类型；onSuccess (Function) - 成功回调；
     *           onError (Function) - 失败回调。
     * 返回值说明：无。
     */
    control(task, action, onSuccess, onError) {
        CurrentTasksRequest.control(task.key, task.repo_id, action, onSuccess, onError);
    }
};

const CurrentTasksUI = {
    /**
     * 用途说明：把任务按钮挂载到顶部栏右侧，避免共用工具栏重绘时丢失入口。
     * 入参说明：无。
     * 返回值说明：无。
     */
    mount() {
        const headerRight = document.querySelector('.header-right');
        if (!headerRight || document.getElementById('btn-current-tasks')) return;

        const button = document.createElement('button');
        button.type = 'button';
        button.id = 'btn-current-tasks';
        button.className = 'icon-btn current-tasks-trigger';
        button.innerHTML = '<img id="current-tasks-icon" class="current-tasks-icon" alt="" aria-hidden="true">';
        headerRight.insertBefore(button, headerRight.firstChild);
        button.addEventListener('click', (event) => {
            event.stopPropagation();
            CurrentTasksApp.toggle();
        });
        this.createPanel();
        this.updateTrigger();

        document.addEventListener('appearance:themechange', () => {
            this.updateTrigger();
            if (CurrentTasksState.open) this.render();
        });
        document.addEventListener('appearance:languagechange', () => {
            this.updateTrigger();
            if (CurrentTasksState.open) this.render();
        });
        document.addEventListener('click', (event) => {
            const panel = document.getElementById('current-tasks-panel');
            if (CurrentTasksState.open && panel && !panel.contains(event.target)
                    && !document.getElementById('btn-current-tasks').contains(event.target)) {
                CurrentTasksApp.close();
            }
        });
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && CurrentTasksState.open) CurrentTasksApp.close();
        });
        window.addEventListener('resize', () => this.position());
        CurrentTasksState.initialized = true;
    },

    /**
     * 用途说明：创建任务弹出面板及空状态、错误状态容器。
     * 入参说明：无。
     * 返回值说明：无。
     */
    createPanel() {
        if (document.getElementById('current-tasks-panel')) return;
        const panel = document.createElement('section');
        panel.id = 'current-tasks-panel';
        panel.className = 'current-tasks-panel hidden';
        panel.setAttribute('role', 'dialog');
        panel.setAttribute('aria-label', 'current_tasks.title');
        panel.innerHTML = `
            <div class="current-tasks-header">
                <div class="current-tasks-heading">
                    <h2 id="current-tasks-title" class="current-tasks-title"></h2>
                    <span id="current-tasks-count" class="current-tasks-count"></span>
                </div>
                <button id="current-tasks-close" type="button" class="current-tasks-close" title="">
                    <span class="theme-icon icon-close" aria-hidden="true"></span>
                </button>
            </div>
            <div id="current-tasks-content" class="current-tasks-content" aria-live="polite"></div>
        `;
        document.body.appendChild(panel);
        document.getElementById('current-tasks-close').addEventListener('click', () => CurrentTasksApp.close());
        document.getElementById('current-tasks-content').addEventListener('click', (event) => this.handleContentClick(event));
    },

    /**
     * 用途说明：根据任务数量切换静态图标、动图和按钮提示。
     * 入参说明：无。
     * 返回值说明：无。
     */
    updateTrigger() {
        const button = document.getElementById('btn-current-tasks');
        const icon = document.getElementById('current-tasks-icon');
        if (!button || !icon) return;
        const hasTasks = CurrentTasksState.tasks.length > 0;
        const theme = document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light';
        const iconName = hasTasks ? 'task_running.svg' : 'task.svg';
        const iconUrl = `/common/themes/${theme}/icons/${iconName}`;
        // 轮询刷新时保持同一图片地址，避免重复下载导致 CSS 旋转动画不断重新开始
        if (icon.getAttribute('src') !== iconUrl) icon.src = iconUrl;
        const label = I18nManager.t(hasTasks ? 'current_tasks.button_active' : 'current_tasks.button_idle', {
            count: CurrentTasksState.tasks.length
        });
        button.title = label;
        button.setAttribute('aria-label', label);
        button.setAttribute('aria-expanded', String(CurrentTasksState.open));
        button.setAttribute('aria-controls', 'current-tasks-panel');
        button.classList.toggle('has-tasks', hasTasks);
    },

    /**
     * 用途说明：刷新面板标题、数量与任务列表；打开时调用。
     * 入参说明：无。
     * 返回值说明：无。
     */
    render() {
        const panel = document.getElementById('current-tasks-panel');
        const content = document.getElementById('current-tasks-content');
        if (!panel || !content) return;
        panel.setAttribute('aria-label', I18nManager.t('current_tasks.title'));
        document.getElementById('current-tasks-title').textContent = I18nManager.t('current_tasks.title');
        document.getElementById('current-tasks-count').textContent = I18nManager.t('current_tasks.count', {
            count: CurrentTasksState.tasks.length
        });
        const close = document.getElementById('current-tasks-close');
        close.title = I18nManager.t('current_tasks.close');
        close.setAttribute('aria-label', I18nManager.t('current_tasks.close'));

        if (CurrentTasksState.loading && CurrentTasksState.tasks.length === 0) {
            content.innerHTML = `<div class="current-tasks-loading"><span class="current-tasks-spinner" aria-hidden="true"></span><span>${this.escape(I18nManager.t('common.loading'))}</span></div>`;
            return;
        }
        if (CurrentTasksState.tasks.length === 0) {
            const theme = document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light';
            content.innerHTML = `
                <div class="current-tasks-empty">
                    <img src="/common/themes/${theme}/icons/task_empty.svg" class="current-tasks-empty-icon" alt="">
                    <p>${this.escape(I18nManager.t('current_tasks.empty'))}</p>
                </div>`;
            return;
        }
        content.innerHTML = CurrentTasksState.tasks.map(task => this.renderTask(task)).join('');
        content.querySelectorAll('.current-tasks-progress-bar').forEach(bar => {
            bar.style.width = `${bar.dataset.percent}%`;
        });
    },

    /**
     * 用途说明：渲染单个任务卡片，包含名称、仓库、状态、进度和可用控制按钮。
     * 入参说明：task (Object) - 后端返回的任务快照。
     * 返回值说明：string - 已转义的任务卡片 HTML。
     */
    renderTask(task) {
        const taskName = I18nManager.t(`current_tasks.type_${task.key}`);
        const paused = task.status === 'paused';
        const percent = task.total > 0 ? Math.max(0, Math.min(100, Math.round(task.current / task.total * 100))) : 0;
        const iconClass = this.taskIcon(task.key);
        const controlKey = `${task.key}:${task.repo_id}`;
        const isControlling = CurrentTasksState.controlling === controlKey;
        const canManage = Boolean(task.can_stop);
        const toggleAction = paused ? 'resume' : 'pause';
        const canToggle = paused ? task.can_resume : task.can_pause;
        return `
            <article class="current-tasks-item${paused ? ' is-paused' : ''}">
                <div class="current-tasks-item-top">
                    <span class="current-tasks-type-icon theme-icon ${iconClass}" aria-hidden="true"></span>
                    <div class="current-tasks-item-heading">
                        <h3 class="current-tasks-item-title">${this.escape(taskName)}</h3>
                        <div class="current-tasks-repo">${this.escape(I18nManager.t('current_tasks.repository', { name: task.repo_name }))}</div>
                    </div>
                    <span class="current-tasks-status${paused ? ' paused' : ''}">${this.escape(I18nManager.t(paused ? 'current_tasks.paused' : 'current_tasks.processing'))}</span>
                </div>
                <div class="current-tasks-progress-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${percent}">
                    <span class="current-tasks-progress-bar${task.total > 0 ? '' : ' indeterminate'}" data-percent="${task.total > 0 ? percent : 35}"></span>
                </div>
                <p class="current-tasks-message">${this.escape(task.message || '')}</p>
                ${canManage ? `
                    <div class="current-tasks-actions">
                        <button type="button" class="current-tasks-action stop" data-task-action="stop" data-task-key="${this.escape(task.key)}" data-task-repo="${task.repo_id}" ${isControlling ? 'disabled' : ''}>
                            <span class="theme-icon icon-close" aria-hidden="true"></span>${this.escape(I18nManager.t('current_tasks.stop'))}
                        </button>
                        ${canToggle ? `
                            <button type="button" class="current-tasks-action" data-task-action="${toggleAction}" data-task-key="${this.escape(task.key)}" data-task-repo="${task.repo_id}" ${isControlling ? 'disabled' : ''}>
                                <span class="theme-icon icon-${paused ? 'play' : 'pause'}" aria-hidden="true"></span>${this.escape(I18nManager.t(paused ? 'current_tasks.resume' : 'current_tasks.pause'))}
                            </button>` : ''}
                    </div>` : ''}
            </article>`;
    },

    /**
     * 用途说明：为任务类型选择已有的主题图标。
     * 入参说明：key (string) - 任务类型标识。
     * 返回值说明：string - 图标 CSS 类名。
     */
    taskIcon(key) {
        const icons = {
            scan: 'icon-refresh', metadata: 'icon-info', duplicate: 'icon-duplicate',
            organize: 'icon-organize', face: 'icon-image', thumbnail: 'icon-image',
            thumbnail_sync: 'icon-refresh', batch_check: 'icon-check', recycle_cleanup: 'icon-trash'
        };
        return icons[key] || 'icon-file';
    },

    /**
     * 用途说明：处理任务按钮的点击事件并转交应用控制流程。
     * 入参说明：event (Event) - 面板内容区域的点击事件。
     * 返回值说明：无。
     */
    handleContentClick(event) {
        const button = event.target.closest('[data-task-action]');
        if (!button || button.disabled) return;
        const task = CurrentTasksState.tasks.find(item => item.key === button.dataset.taskKey
            && Number(item.repo_id) === Number(button.dataset.taskRepo));
        if (task) CurrentTasksApp.control(task, button.dataset.taskAction);
    },

    /**
     * 用途说明：将面板定位到任务按钮下方，并限制在可视区域内。
     * 入参说明：无。
     * 返回值说明：无。
     */
    position() {
        const button = document.getElementById('btn-current-tasks');
        const panel = document.getElementById('current-tasks-panel');
        if (!button || !panel || !CurrentTasksState.open) return;
        const rect = button.getBoundingClientRect();
        const width = Math.min(400, window.innerWidth - 16);
        const left = Math.max(8, Math.min(window.innerWidth - width - 8, rect.right - width));
        const top = Math.min(rect.bottom + 8, window.innerHeight - 120);
        panel.style.left = `${left}px`;
        panel.style.top = `${top}px`;
        panel.style.width = `${width}px`;
        panel.style.maxHeight = `${Math.max(100, window.innerHeight - top - 8)}px`;
    },

    /**
     * 用途说明：显示面板加载失败提示并提供重试入口。
     * 入参说明：message (string) - 失败原因。
     * 返回值说明：无。
     */
    showError(message) {
        const content = document.getElementById('current-tasks-content');
        if (!content || !CurrentTasksState.open) return;
        content.innerHTML = `
            <div class="current-tasks-error">
                <p>${this.escape(message || I18nManager.t('current_tasks.load_failed'))}</p>
                <button id="current-tasks-retry" type="button" class="current-tasks-action">${this.escape(I18nManager.t('current_tasks.retry'))}</button>
            </div>`;
        document.getElementById('current-tasks-retry').addEventListener('click', () => CurrentTasksApp.refresh());
    },

    /**
     * 用途说明：转义动态文本，避免文件名、路径或仓库名注入 HTML。
     * 入参说明：value (string) - 待转义文本。
     * 返回值说明：string - 转义后的安全文本。
     */
    escape(value) {
        return String(value ?? '').replace(/[&<>"']/g, character => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        })[character]);
    }
};

const CurrentTasksApp = {
    /**
     * 用途说明：启动组件、立即刷新任务并开启低频轮询。
     * 入参说明：无。
     * 返回值说明：无。
     */
    start() {
        CurrentTasksUI.mount();
        this.refresh();
        this.startPolling();
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) this.stopPolling();
            else {
                this.refresh();
                this.startPolling();
            }
        });
    },

    /**
     * 用途说明：切换任务面板显示状态，打开时刷新数据。
     * 入参说明：无。
     * 返回值说明：无。
     */
    toggle() {
        if (CurrentTasksState.open) this.close();
        else {
            CurrentTasksState.open = true;
            const panel = document.getElementById('current-tasks-panel');
            panel.classList.remove('hidden');
            CurrentTasksUI.updateTrigger();
            CurrentTasksUI.render();
            CurrentTasksUI.position();
            this.refresh();
        }
    },

    /**
     * 用途说明：关闭任务面板，保留后台轮询。
     * 入参说明：无。
     * 返回值说明：无。
     */
    close() {
        CurrentTasksState.open = false;
        document.getElementById('current-tasks-panel')?.classList.add('hidden');
        CurrentTasksUI.updateTrigger();
    },

    /**
     * 用途说明：刷新任务数据；请求进行中时跳过，避免轮询堆积。
     * 入参说明：无。
     * 返回值说明：无。
     */
    refresh() {
        if (CurrentTasksState.loading || !CurrentTasksState.initialized) return;
        CurrentTasksState.loading = true;
        if (CurrentTasksState.open) CurrentTasksUI.render();
        CurrentTasksAPI.list(
            (response) => {
                CurrentTasksState.loading = false;
                if (response.status !== 'success' || !response.data) {
                    CurrentTasksUI.showError(response.message);
                    return;
                }
                CurrentTasksState.tasks = Array.isArray(response.data.tasks) ? response.data.tasks : [];
                CurrentTasksUI.updateTrigger();
                if (CurrentTasksState.open) CurrentTasksUI.render();
            },
            (error) => {
                CurrentTasksState.loading = false;
                CurrentTasksUI.showError(error?.message);
            }
        );
    },

    /**
     * 用途说明：暂停、恢复或停止任务；停止前要求管理员确认。
     * 入参说明：task (Object) - 目标任务；action (string) - pause/resume/stop。
     * 返回值说明：无。
     */
    control(task, action) {
        const apply = () => {
            CurrentTasksState.controlling = `${task.key}:${task.repo_id}`;
            CurrentTasksUI.render();
            CurrentTasksAPI.control(task, action,
                (response) => {
                    CurrentTasksState.controlling = '';
                    if (response.status === 'success') Toast.show(response.message);
                    else Toast.show(response.message || I18nManager.t('current_tasks.control_failed'));
                    this.refresh();
                },
                (error) => {
                    CurrentTasksState.controlling = '';
                    Toast.show(error?.message || I18nManager.t('current_tasks.control_failed'));
                    CurrentTasksUI.render();
                });
        };
        if (action !== 'stop') {
            apply();
            return;
        }
        const hintKey = task.key === 'face' ? 'current_tasks.stop_hint_face'
            : task.key === 'organize' ? 'current_tasks.stop_hint_organize' : 'current_tasks.stop_hint';
        UIComponents.showConfirmModal({
            title: I18nManager.t('current_tasks.stop_confirm_title'),
            message: I18nManager.t(hintKey, { name: I18nManager.t(`current_tasks.type_${task.key}`) }),
            confirmText: I18nManager.t('current_tasks.stop'),
            onConfirm: apply
        });
    },

    /**
     * 用途说明：开启四秒一次的安静轮询，不显示全局蒙版。
     * 入参说明：无。
     * 返回值说明：无。
     */
    startPolling() {
        this.stopPolling();
        CurrentTasksState.timer = window.setInterval(() => this.refresh(), 4000);
    },

    /**
     * 用途说明：停止轮询，页面隐藏时调用以节省请求。
     * 入参说明：无。
     * 返回值说明：无。
     */
    stopPolling() {
        if (CurrentTasksState.timer !== null) {
            window.clearInterval(CurrentTasksState.timer);
            CurrentTasksState.timer = null;
        }
    }
};
