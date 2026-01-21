/**
 * 用途说明：ProgressButtonWidget 测试页面的逻辑处理，模拟各种异步任务场景。
 */

const TestApp = {
    /**
     * 用途说明：初始化测试页面，设置顶部导航并挂载测试用例。
     */
    init() {
        UIComponents.initHeader('组件测试: ProgressButton', true, '../home/home.html');
        this.initTestCase1();
        this.initTestCase2();
    },

    /**
     * 用途说明：初始化测试用例 1 - 模拟进度条增加。
     * 逻辑说明：点击开始后启动定时器，每 100ms 增加 1% 进度。
     */
    initTestCase1() {
        const container = document.getElementById('btn-container-1');
        const log = document.getElementById('log-1');
        let timer = null;
        let progress = 0;
        const total = 100;

        const btn = ProgressButtonWidget.create({
            normalText: '开始模拟任务',
            stopText: '取消任务',
            onStart: () => {
                log.innerText = '任务已启动...';
                progress = 0;
                btn.setState('processing');
                btn.setProgress(0, `正在处理：0/${total}`);

                timer = setInterval(() => {
                    progress += 1;
                    // 设置进度时同时设置文案，格式为（正在处理：1/100）
                    btn.setProgress(progress, `正在处理：${progress}/${total}`);

                    if (progress >= total) {
                        clearInterval(timer);
                        btn.setState('idle');
                        log.innerText = '任务完成！状态已重置为 idle。';
                        Toast.show('任务模拟成功完成');
                    }
                }, 100);
            },
            onStop: () => {
                if (timer) clearInterval(timer);
                btn.setState('idle');
                log.innerText = `任务被手动停止。最后进度: ${progress}%`;
                Toast.show('任务已停止');
            }
        });

        container.appendChild(btn.getElement());
    },

    /**
     * 用途说明：初始化测试用例 2 - 测试自定义外观。
     * 逻辑说明：展示不同背景色的按钮，并直接触发进度变化。
     */
    initTestCase2() {
        const container = document.getElementById('btn-container-2');
        const log = document.getElementById('log-2');

        const btn = ProgressButtonWidget.create({
            normalText: '紫色风格按钮',
            stopText: '别点我',
            defaultBgColor: '#6f42c1', // 紫色
            onStart: () => {
                log.innerText = '正在执行特殊任务...';
                btn.setState('processing');
                // 设置固定进度的文案
                btn.setProgress(50, '正在处理：50/100');
            },
            onStop: () => {
                btn.setState('idle');
                log.innerText = '特殊任务已中止。';
            }
        });

        container.appendChild(btn.getElement());
    }
};

document.addEventListener('DOMContentLoaded', () => TestApp.init());
