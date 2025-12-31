from flask import jsonify
from backend.common.log_utils import LogUtils

def success_response(message="操作成功", data=None):
    """
    用途：构建成功的 API 响应
    入参说明：
        - message: 成功提示信息，默认为"操作成功"
        - data: 返回的数据对象，可选
    返回值说明：JSON 格式的成功响应和 200 状态码
    """
    response = {
        "status": "success",
        "message": message
    }
    if data is not None:
        response["data"] = data
    
    # 使用 debug 级别记录返回内容
    LogUtils.debug(f"Success Response: {response}")
    
    return jsonify(response), 200

def error_response(message, code=400):
    """
    用途：构建失败的 API 响应
    入参说明：
        - message: 错误提示信息
        - code: HTTP 状态码，默认为 400
    返回值说明：JSON 格式的错误响应和对应的状态码
    """
    return jsonify({
        "status": "error",
        "message": message
    }), code
