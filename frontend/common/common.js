/**
 * 通用工具类
 */
const CommonUtils = {
    /**
     * 格式化文件大小，将字节数转换为 B, KB, MB, GB 等单位
     * @param {number} bytes - 文件字节大小
     * @returns {string} 格式化后的带单位的字符串
     */
    formatFileSize: function(bytes) {
        if (bytes === 0) return '0 B';
        if (!bytes) return '-';
        
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        // 返回保留两位小数的格式化字符串
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },

    /**
     * 用途说明：将视频时长（秒）转换为 HH:mm:ss 格式。
     * 入参说明：seconds (number) - 视频总时长（秒）。
     * 返回值说明：String - 格式化后的时长字符串。
     */
    formatDuration: function(seconds) {
        if (seconds === null || seconds === undefined || isNaN(seconds)) return 'N/A';
        const s = Math.floor(seconds);
        if (s <= 0) return '00:00:00';

        const hours = Math.floor(s / 3600);
        const minutes = Math.floor((s % 3600) / 60);
        const remainingSeconds = s % 60;

        return [hours, minutes, remainingSeconds]
            .map(v => v < 10 ? "0" + v : v)
            .join(":");
    },

    /**
     * 用途说明：将日期转换为友好显示格式。如果是今天、昨天、前天，则返回对应的描述文字；否则返回 yyyy/MM/dd。
     * 入参说明：dateInput (String|Date|Number) - 可被解析为日期的输入值。
     * 返回值说明：String - 格式化后的日期字符串。
     */
    formatFriendlyDate: function(dateInput) {
        if (!dateInput) return '-';
        const date = new Date(dateInput);
        if (isNaN(date.getTime())) return '-';

        const now = new Date();
        // 获取今天、目标日期的零点时间进行比较
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const targetDate = new Date(date.getFullYear(), date.getMonth(), date.getDate());
        
        const diffTime = today.getTime() - targetDate.getTime();
        const diffDays = Math.round(diffTime / (1000 * 60 * 60 * 24));

        if (diffDays === 0) return '今天';
        if (diffDays === 1) return '昨天';
        if (diffDays === 2) return '前天';

        // 格式化为 yyyy/MM/dd
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}/${month}/${day}`;
    }
};
