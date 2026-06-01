"""
GOP 预授权审核系统 - Flask 应用入口
重构后的架构：使用蓝图分组路由，业务逻辑在服务层
"""
import os
from flask import Flask

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

# 初始化日志
from app.logger import logger
logging = logger.setup_logger()

# 导入错误处理中间件
from app.api.middleware.error_handler import register_error_handlers

# 导入路由蓝图
from app.api.routes.claim_routes import claim_bp
from app.api.routes.document_routes import document_bp
from app.api.routes.sync_routes import sync_bp


def create_app() -> Flask:
    """应用工厂函数"""
    app = Flask(__name__)
    
    # 配置
    app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB 请求体上限
    
    # 注册错误处理器
    register_error_handlers(app)
    
    # 注册蓝图
    app.register_blueprint(claim_bp)
    app.register_blueprint(document_bp)
    app.register_blueprint(sync_bp)
    
    # 健康检查端点
    @app.route('/health', methods=['GET'])
    def health_check():
        return {"status": "healthy"}, 200
    
    logging.info("GOP 预授权审核系统启动完成")
    return app


# 创建应用实例
app = create_app()


if __name__ == '__main__':
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    logging.info(f"启动 Flask 应用，调试模式: {debug_mode}")
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)