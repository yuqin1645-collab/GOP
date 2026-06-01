# GOP 系统重构迁移指南

## 概述

本次重构将 `app.py`（1048行）中的业务逻辑和路由拆分到独立的服务层和路由模块中，采用分层架构提高代码可维护性和可测试性。

## 新架构目录结构

```
GOP/
├── app_new.py                        # 重构后的应用入口（使用蓝图）
├── app.py                            # 原始应用（保留作为参考）
├── api/                              # API 层
│   ├── middleware/
│   │   └── error_handler.py          # 统一错误处理
│   └── routes/
│       ├── claim_routes.py           # 理赔相关路由
│       ├── document_routes.py        # 文档处理路由
│       └── sync_routes.py            # 同步相关路由
├── services/                         # 业务服务层（新增）
│   ├── claim_service.py              # 理赔业务服务
│   ├── policy_service.py             # 保单策略服务
│   └── sync_service.py               # 同步服务
├── config/                           # 配置管理（新增）
│   └── settings.py                   # 配置类
├── models/                           # 数据模型（新增）
│   └── claim.py                      # 理赔案件模型
├── dao/                              # 数据访问层（保持不变）
├── llm/                              # LLM服务层（保持不变）
└── utils/                            # 工具层（保持不变）
```

## 迁移步骤

### 方式一：渐进式迁移（推荐）

1. **备份原始文件**
   ```bash
   cp app.py app_backup_original.py
   ```

2. **测试新应用**
   ```bash
   python app_new.py
   ```
   验证所有 API 端点是否正常工作。

3. **替换原应用**
   确认新应用正常后，替换原文件：
   ```bash
   mv app.py app_legacy.py
   mv app_new.py app.py
   ```

### 方式二：并行运行

保留 `app.py` 作为传统入口，同时可以使用 `app_new.py` 进行新功能开发。

## API 端点映射

所有 API 端点路径保持不变，只是内部实现从路由函数迁移到服务层：

| API 端点 | 原实现位置 | 新实现位置 |
|----------|-----------|-----------|
| `POST /api/initPreAuth` | app.py:237 | api/routes/claim_routes.py:21 |
| `POST /api/initRePreAuth` | app.py:274 | api/routes/claim_routes.py:58 |
| `POST /api/genPreAuthResult` | app.py:311 | api/routes/claim_routes.py:91 |
| `POST /api/genPreAuthResultMultiThread` | app.py:353 | api/routes/claim_routes.py:128 |
| `POST /api/processBasicInfo` | app.py:429 | api/routes/claim_routes.py:189 |
| `POST /api/processPoliciesInfo` | app.py:473 | api/routes/document_routes.py:26 |
| `POST /api/processDocumentsInfo` | app.py:596 | api/routes/document_routes.py:14 |
| `POST /api/processProviderInfo` | app.py:774 | api/routes/sync_routes.py:38 |
| `POST /api/processBlackListMemberInfo` | app.py:810 | api/routes/sync_routes.py:50 |
| `POST /api/syncEccsResult` | app.py:854 | api/routes/sync_routes.py:22 |
| `POST /api/processCptCodes` | app.py:955 | api/routes/sync_routes.py:62 |

## 新增功能

### 1. 统一错误处理

所有 API 现在使用统一的错误响应格式：
```json
{
  "error": "ERROR_CODE",
  "message": "错误描述"
}
```

可用错误类型：
- `AppError` - 应用自定义异常
- `BusinessError` - 业务逻辑异常 (400)
- `ValidationError` - 参数验证异常 (400)
- `ExternalAPIError` - 外部 API 调用异常 (502)
- `LLMServiceError` - LLM 服务异常 (502)

### 2. 健康检查端点

新增 `GET /health` 端点用于健康检查：
```bash
curl http://localhost:5000/health
# 返回: {"status": "healthy"}
```

### 3. 配置管理

新增 `config/settings.py` 提供类型安全的配置管理：
```python
from config.settings import config
config.validate()  # 验证配置
config.database.connection_string  # 获取连接字符串
```

## 回滚方案

如果新架构出现问题，可以立即回滚：

```bash
# 恢复原始应用
mv app.py app_new.py
mv app_backup_original.py app.py

# 重启服务
python app.py
```

## 后续优化建议

1. **添加单元测试** - 服务层现在可以独立测试
2. **添加 API 版本控制** - 如 `/api/v1/...`
3. **优化连接池配置** - 使用 `config/settings.py` 管理
4. **添加请求日志中间件** - 记录请求耗时
5. **实现缓存层** - 对频繁查询的数据进行缓存

## 注意事项

- 所有环境变量配置保持不变
- 数据库连接池配置保持不变
- LLM 服务调用方式保持不变
- 外部 API 调用方式保持不变
