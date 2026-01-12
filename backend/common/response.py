from typing import Any, Tuple

from flask import jsonify, request

from backend.common.log_utils import LogUtils


def success_response(message: str = "操作成功", data: Any = None) -> Tuple[Any, int]:
    """
    用途：构建成功的 API 响应
    入参说明：
        - message: str, 成功提示信息，默认为"操作成功"
        - data: Any, 返回的数据对象，可选
    返回值说明：Tuple[Any, int], 包含 JSON 格式的成功响应和 200 状态码的元组
    """
    response: dict = {
        "status": "success",
        "message": message
    }
    if data is not None:
        response["data"] = data
    
    # 记录 API 响应日志
    LogUtils.api_response(request.path, 200, response)
    
    return jsonify(response), 200

def error_response(message: str, code: int = 400) -> Tuple[Any, int]:
    """
    用途：构建失败的 API 响应
    入参说明：
        - message: str, 错误提示信息
        - code: int, HTTP 状态码，默认为 400
    返回值说明：Tuple[Any, int], 包含 JSON 格式的错误响应和对应状态码的元组
    """
    response: dict = {
        "status": "error",
        "message": message
    }
    
    # 记录 API 响应日志
    LogUtils.api_response(request.path, code, response)
    
    return jsonify(response), code
