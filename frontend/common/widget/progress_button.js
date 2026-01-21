/**
 * 进度条按钮组件 (ProgressButtonWidget)
 *
 * 使用说明：
 * 1. 引入本文件后，通过 ProgressButtonWidget.create(options) 创建按钮控制器。
 * 2. 将控制器的 getElement() 返回的 DOM 元素添加到目标容器中。
 * 3. 使用 setState('processing') 切换至进度条模式，使用 setProgress(value, message) 更新进度。
 * 4. 任务结束时调用 setState('idle') 恢复初始状态。
 *
 * 提供一个具有双层背景、显式状态管理及自定义默认背景色的按钮。
 */
const ProgressButtonWidget = {
    /**
     * 用途说明：创建一个进度条按钮实例。
     * 入参说明：
     *   options (Object): 配置对象
     *     - normalText (String): 无任务状态（idle）时的按钮文字。
     *     - stopText (String): 任务进行中（processing）且鼠标悬停时的停止文案。
     *     - defaultBgColor (String): 无任务状态下的背景颜色，默认为 '#f0f0f0'。
     *     - onStart (Function): idle 状态下点击按钮的回调。
     *     - onStop (Function): processing 状态下点击按钮的回调。
     * 返回值说明：Object - 包含 setState, setProgress 和 getElement 方法的按钮控制器。
     */
    create: function(options) {
        const settings = {
            normalText: options.normalText || '开始任务',
            stopText: options.stopText || '停止任务',
            defaultBgColor: options.defaultBgColor || '#f0f0f0',
            onStart: options.onStart || (() => {}),
            onStop: options.onStop || (() => {})
        };

        // 内部状态
        let state = 'idle'; // 'idle' 或 'processing'
        let currentProgress = 0;
        let currentMessage = ''; // 当前自定义进度文案

        // --- DOM 构建 ---
        const container = document.createElement('div');
        container.className = 'progress-btn-container';
        // 初始设置自定义背景色
        container.style.backgroundColor = settings.defaultBgColor;

        const fillLayer = document.createElement('div');
        fillLayer.className = 'progress-btn-fill';

        const textLayer = document.createElement('span');
        textLayer.className = 'progress-btn-text';
        textLayer.innerText = settings.normalText;

        container.appendChild(fillLayer);
        container.appendChild(textLayer);

        /**
         * 用途说明：内部方法，根据当前状态和进度刷新 UI 显示。
         * 返回值说明：void
         */
        const refreshUI = () => {
            if (state === 'processing') {
                container.classList.add('processing');
                fillLayer.style.width = currentProgress + '%';
                // 确保在进行中且非悬停时显示默认背景色及进度文字
                if (!container.matches(':hover')) {
                    container.style.backgroundColor = settings.defaultBgColor;
                    textLayer.innerText = currentMessage || `${currentProgress}%`;
                }
            } else {
                container.classList.remove('processing');
                // 恢复自定义默认背景色
                container.style.backgroundColor = settings.defaultBgColor;
                fillLayer.style.width = '0%';
                textLayer.innerText = settings.normalText;
                currentMessage = ''; // 重置状态
            }
        };

        // --- 事件绑定 ---

        // 鼠标移入逻辑
        container.addEventListener('mouseenter', () => {
            if (state === 'processing') {
                textLayer.innerText = settings.stopText;
                // 只有在显示 stopText 的时候背景色才变红
                container.style.backgroundColor = '#c82333';
            }
        });

        // 鼠标移出逻辑
        container.addEventListener('mouseleave', () => {
            // 移出后始终恢复自定义默认背景色
            container.style.backgroundColor = settings.defaultBgColor;
            if (state === 'processing') {
                textLayer.innerText = currentMessage || `${currentProgress}%`;
            } else {
                textLayer.innerText = settings.normalText;
            }
        });

        // 点击逻辑
        container.addEventListener('click', (e) => {
            e.stopPropagation();
            if (state === 'processing') {
                settings.onStop();
            } else {
                settings.onStart();
            }
        });

        // --- 暴露接口 ---
        return {
            /**
             * 用途说明：设置按钮的状态。
             * 入参说明：newState (String) - 'idle' (无任务) 或 'processing' (正在进行)。
             * 返回值说明：void
             */
            setState: function(newState) {
                if (newState === 'idle' || newState === 'processing') {
                    state = newState;
                    refreshUI();
                }
            },

            /**
             * 用途说明：设置当前进度值及可选的进度文案。
             * 入参说明：
             *   value (Number): 0 到 100 之间的数值。
             *   message (String): 可选，自定义显示的进度文案。如果不提供，则默认显示百分比。
             * 返回值说明：void
             */
            setProgress: function(value, message = '') {
                currentProgress = Math.min(100, Math.max(0, value));
                currentMessage = message;
                if (state === 'processing') {
                    refreshUI();
                }
            },

            /**
             * 用途说明：获取生成的按钮 DOM 元素。
             * 返回值说明：HTMLElement - 按钮容器。
             */
            getElement: function() {
                return container;
            }
        };
    }
};
