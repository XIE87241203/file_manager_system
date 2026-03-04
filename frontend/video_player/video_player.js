/**
 * 用途说明：视频播放页面逻辑处理，负责页面初始化、多语言渲染及 ArtPlayer 播放器集成。
 */

const VideoPlayerApp = {
    /** @type {Artplayer|null} 播放器实例 */
    art: null,

    /**
     * 用途说明：初始化播放器页面，包括多语言环境、标题栏及播放器加载。
     * 入参说明：无
     * 返回值说明：无
     */
    init() {
        // 1. 初始化多语言环境
        I18nManager.init();
        I18nManager.render();

        // 2. 获取 URL 参数
        /** @type {URLSearchParams} */
        const urlParams = new URLSearchParams(window.location.search);
        /** @type {string|null} */
        const filePath = urlParams.get('path');

        if (!filePath) {
            Toast.show(I18nManager.t('video_player.no_path'));
            return;
        }

        /** @type {string} */
        const fileName = UIComponents.getFileName(filePath);

        // 3. 初始化通用头部
        HeaderToolbar.init({
            title: fileName,
            showBack: true,
            theme: 'dark'
        });

        // 4. 初始化 ArtPlayer
        this.initArtPlayer(filePath, fileName);
    },

    /**
     * 用途说明：初始化 ArtPlayer 播放器并配置流地址、旋转插件及错误处理。
     * 入参说明：
     *   - filePath (string): 视频文件的绝对路径
     *   - fileName (string): 视频文件名
     * 返回值说明：无
     */
    initArtPlayer(filePath, fileName) {
        // 使用封装后的请求工具获取流地址
        /** @type {string|null} */
        const streamUrl = VideoPlayerRequest.getVideoStreamUrl(filePath);

        if (!streamUrl) {
            Toast.show(I18nManager.t('common.login_expired'));
            return;
        }

        // 获取当前系统语言并映射到 ArtPlayer 支持的格式
        const artLang = I18nManager.currentLang === 'zh' ? 'zh-cn' : 'en';

        this.art = new Artplayer({
            container: '#artplayer-container',
            url: streamUrl,
            title: fileName,
            lang: artLang, // 设置播放器界面语言
            autoplay: true,
            autoSize: false,
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
            autoPlayback: true,
            controlsList: ['nodownload'],
            settings: [
                {
                    html: I18nManager.t('video_player.rotate'),
                    tooltip: I18nManager.t('video_player.portrait'),
                    switch: false,
                    /**
                     * 用途说明：在设置菜单中切换整个网页的横屏显示模式。
                     * 入参说明：
                     *   - item (object): 当前设置项配置对象。
                     *   - art (object): ArtPlayer 实例对象。
                     * 返回值说明：
                     *   - (boolean): 返回切换后的开关状态。
                     */
                    onSwitch: function (item, art) {
                        const newState = !item.switch;
                        document.body.classList.toggle('page-landscape', newState);
                        item.switch = newState;
                        item.tooltip = newState ? I18nManager.t('video_player.landscape') : I18nManager.t('video_player.portrait');

                        const playerInstance = art || VideoPlayerApp.art;
                        if (playerInstance && playerInstance.setting && typeof playerInstance.setting.update === 'function') {
                            playerInstance.setting.update(item);
                        }
                        window.dispatchEvent(new Event('resize'));
                        return newState;
                    },
                },
            ],
        });

        // 监听错误
        this.art.on('error', (error) => {
            console.error('ArtPlayer Error:', error);
            Toast.show(I18nManager.t('video_player.load_failed'));
        });

        // 预防快捷键下载
        document.onkeydown = (e) => {
            if (e.ctrlKey && (e.key === 's' || e.key === 'u')) {
                e.preventDefault();
                return false;
            }
        };
    }
};

document.addEventListener('DOMContentLoaded', () => VideoPlayerApp.init());
