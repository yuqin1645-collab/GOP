"""
统一错误处理中间件
提供标准化的错误响应格式和异常处理机制
"""
from flask import jsonify, current_app
from app.logger import setup_logger

logging = setup_logger()


class AppError(Exception):
    """应用自定义异常基类"""
    
    def __init__(self, message: str, status_code: int = 500, error_code: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code or 'INTERNAL_ERROR'


class BusinessError(AppError):
    """业务逻辑异常"""
    
    def __init__(self, message: str, error_code: str = 'BUSINESS_ERROR'):
        super().__init__(message, status_code=400, error_code=error_code)


class ValidationError(AppError):
    """参数验证异常"""
    
    def __init__(self, message: str, field: str = None):
        error_code = 'VALIDATION_ERROR'
        if field:
            error_code = f'VALIDATION_ERROR_{field.upper()}'
        super().__init__(message, status_code=400, error_code=error_code)


class ExternalAPIError(AppError):
    """外部 API 调用异常"""
    
    def __init__(self, message: str, api_name: str = None):
        error_code = 'EXTERNAL_API_ERROR'
        if api_name:
            error_code = f'EXTERNAL_API_ERROR_{api_name.upper()}'
        super().__init__(message, status_code=502, error_code=error_code)


class LLMServiceError(AppError):
    """LLM 服务异常"""
    
    def __init__(self, message: str):
        super().__init__(message, status_code=502, error_code='LLM_SERVICE_ERROR')


def register_error_handlers(app):
    """注册全局错误处理器"""
    
    @app.errorhandler(AppError)
    def handle_app_error(error):
        """处理应用自定义异常"""
        response = jsonify({
            'error': error.error_code,
            'message': str(error)
        })
        return response, error.status_code
    
    @app.errorhandler(400)
    def handle_bad_request(error):
        """处理 400 错误"""
        return jsonify({
            'error': 'BAD_REQUEST',
            'message': str(error.description) if hasattr(error, 'description') else '请求参数错误'
        }), 400
    
    @app.errorhandler(404)
    def handle_not_found(error):
        """处理 404 错误"""
        return jsonify({
            'error': 'NOT_FOUND',
            'message': '请求的资源不存在'
        }), 404
    
    @app.errorhandler(405)
    def handle_method_not_allowed(error):
        """处理 405 错误"""
        return jsonify({
            'error': 'METHOD_NOT_ALLOWED',
            'message': '请求方法不被允许'
        }), 405
    
    @app.errorhandler(500)
    def handle_internal_error(error):
        """处理 500 错误"""
        logging.exception("服务器内部错误")
        return jsonify({
            'error': 'INTERNAL_ERROR',
            'message': '服务器内部错误，请稍后重试'
        }), 500
    
    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        """处理未预期的异常"""
        logging.exception("未预期的异常")
        return jsonify({
            'error': 'UNEXPECTED_ERROR',
            'message': '系统发生未知错误'
        }), 500


def format_error_response(error_code: str, message: str, details: dict = None) -> dict:
    """格式化错误响应"""
    response = {
        'error': error_code,
        'message': message
    }
    if details:
        response['details'] = details
    return response


def format_success_response(data: dict = None, message: str = "success") -> dict:
    """格式化成功响应"""
    response = {
        'status': 'success',
        'message': message
    }
    if data:
        response['data'] = data
    return response
