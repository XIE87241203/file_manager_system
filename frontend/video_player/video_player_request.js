/**
 * 用途说明：封装视频播放相关的 API 请求及资源地址获取逻辑。
 */
const VideoPlayerRequest = {
    /**
     * 用途说明：生成带身份验证 Token 的视频流直链地址。
     * 入参说明：
     *   - filePath (string): 视频文件在服务器上的绝对路径。
     * 返回值说明：
     *   - (string|null): 成功返回完整的流地址 URL，若未登录或缺少 Token 则返回 null。
     */
    getVideoStreamUrl(filePath) {
        /** @type {string|null} */
        const token = Request.getCookie('token');
        if (!token) return null;

        /** @type {string} */
        const baseUrl = Request.baseUrl;
        return `${baseUrl}/api/file_repository/video/stream?path=${encodeURIComponent(filePath)}&token=${encodeURIComponent(token)}`;
    }
};
