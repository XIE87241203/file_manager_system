/**
 * 用途说明：视频播放页面逻辑处理，负责页面初始化、通用头部加载及 ArtPlayer 播放器集成。
 */

const VideoPlayerApp = {
    /** @type {Artplayer|null} 播放器实例 */
    art: null,

    /**
     * 用途说明：初始化播放器页面
     * 入参说明：无
     * 返回值说明：无
     */
    init() {
        // 1. 获取 URL 参数
        /** @type {URLSearchParams} */
        const urlParams = new URLSearchParams(window.location.search);
        /** @type {string|null} */
        const filePath = urlParams.get('path');

        if (!filePath) {
            Toast.show('未指定播放路径');
            return;
        }

        /** @type {string} */
        const fileName = UIComponents.getFileName(filePath);

        // 2. 初始化通用头部
        HeaderToolbar.init({
            title: fileName,
            showBack: true,
            theme: 'dark'
        });

        // 3. 初始化 ArtPlayer
        this.initArtPlayer(filePath, fileName);
    },

    /**
     * 用途说明：初始化 ArtPlayer 播放器并配置相关参数
     * 入参说明：
     *   - filePath (string): 视频文件的绝对路径
     *   - fileName (string): 视频文件名
     * 返回值说明：无
     */
    initArtPlayer(filePath, fileName) {
        /** @type {string|null} */
        const token = Request.getCookie('token');
        if (!token) {
            Toast.show('登录已过期，请重新登录');
            return;
        }

        // 构建带 Token 的流地址
        /** @type {string} */
        const streamUrl = `${Request.baseUrl}/api/file_repository/video/stream?path=${encodeURIComponent(filePath)}&token=${encodeURIComponent(token)}`;

        this.art = new Artplayer({
            container: '#artplayer-container',
            url: streamUrl,
            title: fileName,
            autoplay: true,
            autoSize: false, // 改为 false，由 CSS 控制容器尺寸，播放器填充容器
            playbackRate: true,
            aspectRatio: true,
            setting: true,
            hotkey: true,
            pip: true,
            fullscreen: true,
            fullscreenWeb: true,
            miniProgressBar: true,
            lock: false,
            fastForward: true,
            autoPlayback: true, // 自动续播
            controlsList: ['nodownload'],
            settings: [
                {
                    html: '全屏旋转',
                    tooltip: '竖屏',
                    switch: false,
                    /**
                     * 用途说明：在设置菜单中切换整个网页的横屏显示模式（通过旋转 body 实现）
                     * 入参说明：
                     *   - item (object): 当前设置项配置对象，包含 html, tooltip, switch 等属性
                     *   - art (object): ArtPlayer 实例对象
                     * 返回值说明：
                     *   - (boolean): 返回切换后的开关状态（true 为开启/横屏，false 为关闭/竖屏）
                     */
                    onSwitch: function (item, art) {
                        // 1. 获取目标状态（取反当前状态）
                        /** @type {boolean} */
                        const newState = !item.switch;

                        // 2. 根据最新的开关状态切换 body 的 class
                        document.body.classList.toggle('page-landscape', newState);

                        // 3. 更新设置项对象的属性
                        item.switch = newState;
                        item.tooltip = newState ? '横屏' : '竖屏';

                        // 4. 安全地通知播放器重新渲染该设置项
                        // 增加防御性检查，防止 art.setting 为 undefined 导致脚本中断
                        /** @type {Artplayer} */
                        const playerInstance = art || VideoPlayerApp.art;
                        if (playerInstance && playerInstance.setting && typeof playerInstance.setting.update === 'function') {
                            playerInstance.setting.update(item);
                        }

                        // 5. 强制更新播放器尺寸以适配旋转后的布局
                        window.dispatchEvent(new Event('resize'));

                        // 6. 返回新状态给 ArtPlayer 以便同步 UI
                        return newState;
                    },
                },
            ],
            controls: [],
            plugins: [],
        });

        // 监听错误
        this.art.on('error', (error) => {
            console.error('ArtPlayer Error:', error);
            Toast.show('视频加载失败，请检查文件格式或网络');
        });

        // 额外的安全措施：防止通过快捷键（如 F12, Ctrl+S）尝试下载（仅基础防护）
        document.onkeydown = (e) => {
            if (e.ctrlKey && (e.key === 's' || e.key === 'u')) {
                e.preventDefault();
                return false;
            }
        };
    }
};

document.addEventListener('DOMContentLoaded', () => VideoPlayerApp.init());
