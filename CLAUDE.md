# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

GOP (Guarantee of Payment) 预授权审核系统 — 基于 Flask + 阿里云 DashScope (通义千问) 的医疗保险 AI 预授权审核平台。系统自动分析理赔申请资料、医疗文档和保单条款，生成智能化预授权审核结果。

## 开发常用命令

### 启动服务

```bash
# 开发模式（热重载）
python app.py

# 生产模式（gunicorn，后台运行）
./start_gunicorn.sh

# 停止 gunicorn
./stop_gunicorn.sh
```

### 虚拟环境

项目使用 `myenv` 虚拟环境：

```bash
# Windows
myenv\Scripts\activate

# Linux / macOS
source myenv/bin/activate
```

### 安装依赖

```bash
pip install -r requirements.txt
```

### 环境变量

配置文件为 `.env`（不在仓库中），必需变量：

| 变量 | 说明 |
|------|------|
| `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` | MySQL 连接配置 |
| `api_key` | 阿里云 DashScope API Key |
| `base_url` | DashScope API 地址（默认 `https://dashscope.aliyuncs.com`） |
| `getGopClaimListUrl`, `getClaimInfoApiUrl`, `getPolicyWordingUrl`, `getDocumentsUrl`, `updatePreAuthResultUrl` | 外部系统 API 地址 |
| `eccsWebUrlBase` | ECCS 系统 API 基础地址 |
| `MODEL_DOCUMENT_ANALYSIS` | 文档分析模型，默认 `qwen-vl-plus` |
| `MODEL_DOCUMENT_QVQ` | QVQ 交叉验证模型，默认 `qvq-plus-latest` |
| `MODEL_TEXT_ANALYSIS` | 文本分析模型，默认 `qwen3.5-plus` |
| `MODEL_LONG_DOCUMENT` | 长文档处理模型，默认 `qwen-long-latest` |

### 日志

应用日志路径：`D:/GopLogs/app.log`（由 `logger/logger.py` 配置）

## 系统架构

```
Flask API (app.py)
  │
  ├── DAO 层 (dao/) ── MySQL 数据访问，使用连接池 (utils/db_utils.py)
  ├── LLM 服务层 (llm/) ── 阿里云 DashScope 模型调用
  └── 工具层 (utils/) ── 图片处理、文件下载、外部 API 调用等
```

### 核心处理流水线（5步）

理赔案件按顺序经过以下 API 端点处理，**必须按顺序调用**：

| 步骤 | API | 功能 |
|------|-----|------|
| 1 | `POST /api/initPreAuth` | 从外部系统获取待处理理赔申请列表 |
| 2 | `POST /api/processBasicInfo` | 获取理赔基本信息并存储 |
| 3 | `POST /api/processPoliciesInfo` | 下载并分析保单条款 PDF（`qwen-long-latest`） |
| 4 | `POST /api/processDocumentsInfo` | 下载并分析理赔资料图片（`qwen-vl-plus` + `qvq-plus` 交叉验证） |
| 5 | `POST /api/genPreAuthResultMultiThread` | 综合分析所有结果，生成预授权决策（`qwen3.5-plus`） |

额外端点：
- `POST /api/initRePreAuth` — 重新初始化预授权（RE 审核）
- `POST /api/processProviderInfo` — 同步医疗机构信息
- `POST /api/processBlackListMemberInfo` — 同步黑名单成员
- `POST /api/syncEccsResult` — 同步 ECCS 审核结果
- `POST /api/processCptCodes` — 处理 CPT 编码

### 预授权决策流程（步骤5 内部）

`process_claim_analysis()` 函数整合各阶段分析结果：
1. 获取基本信息、文档分析、保单条款分析结果
2. 提取住院指针、APV 信息、除外治疗/药品信息
3. 获取医院信息（`HospitalInfo` 类）和价格知识库（DashScope Application）
4. 执行两级预分析优化（`pre_analyze_preauth_result1/2`），可能提前返回结果
5. 若预分析未命中，调用完整分析 `analyze_preauth_result()`
6. 将结果写入数据库并回调外部 API

## 目录结构

| 目录/文件 | 说明 |
|-----------|------|
| `app.py` | Flask 主文件，所有 API 端点定义 |
| `dao/` | 数据访问层（ClaimCase、DocumentAnalysis、PoliciesAnalysis、BasicInfoAnalyzedAnalysis、Provider、BlacklistMember、GopConfig、Prompt 等 DAO） |
| `llm/` | LLM 服务层 — `analysis_service.py`（DashScope 调用封装）、`analysis_service_agent.py`（Agent 模式）、`compare_ocr_results.py`（OCR 交叉验证） |
| `utils/` | 工具类 — `image_utils.py`（图片处理）、`image_quality.py`（质量评估）、`file_utils.py`（文件下载）、`api_utils.py`（外部 API）、`db_utils.py`（连接池）、`dao_context.py`（DAO 上下文管理器）、`hospital_info.py`（医院信息）、`email_utils.py`、`cpt_utils.py` |
| `logger/` | 日志配置 |
| `docs/` | 项目文档（README、RESTART_GUIDE、TROUBLESHOOTING） |

## 数据库表

核心表：`claim_case`（理赔主表）、`basic_info_analysis`（基本信息分析）、`document_analysis`（文档分析）、`policies_analysis`（保单分析）、`prompt`（提示词模板）、`gop_config`（业务配置）、`provider`（医疗机构）、`blacklist_member`（黑名单）

详细表结构见 `docs/README.md`。

## 关键设计细节

- **连接池**：使用 `dbutils.PooledDB`（`utils/db_utils.py`），`maxconnections=10`
- **DAO 上下文**：`utils/dao_context.py` 提供 `with dao_context() as (...)` 语法，统一管理 DAO 实例
- **线程安全**：多线程处理（步骤3/4/5）使用 `threading.Lock()` 保护共享 DAO 操作
- **OCR 交叉验证**：每张图片用两个不同模型（`qwen-vl-plus` 和 `qvq-plus`）分析，比较一致性（`llm/compare_ocr_results.py`）
- **提示词存储**：所有 LLM 提示词存储在数据库 `prompt` 表中，通过 `PromptDAO` 动态读取
- **图片处理**：`utils/image_utils.py` 包含完整的图片下载、验证、压缩、base64 转换流程
