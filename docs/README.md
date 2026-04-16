# GOP 预授权审核系统

## 项目概述

GOP (Guarantee of Payment) 预授权审核系统是一个基于人工智能的医疗保险预授权审核平台。系统通过阿里云通义千问大模型自动分析理赔申请资料、医疗文档和保单条款，生成智能化的预授权审核结果。

### 核心功能

- **理赔申请管理**：接收、存储和管理理赔申请数据
- **医疗文档分析**：使用视觉语言模型分析医疗票据、检查报告等图片资料
- **保单条款解析**：使用长文档处理模型分析PDF保单条款
- **智能审核决策**：综合分析结果生成预授权审核结论

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                           Flask API 服务                             │
├─────────────────────────────────────────────────────────────────────┤
│  /api/initPreAuth         - 初始化预授权申请                         │
│  /api/initRePreAuth       - 重新审核预授权                           │
│  /api/processBasicInfo    - 处理基本信息和查询理赔数据                │
│  /api/processPoliciesInfo - 处理保单条款PDF                          │
│  /api/processDocumentsInfo - 处理理赔资料图片                         │
│  /api/genPreAuthResult    - 生成预授权审核结果（单线程）              │
│  /api/genPreAuthResultMultiThread - 生成预授权审核结果（多线程）      │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         LLM 分析服务层                               │
├─────────────────────────────────────────────────────────────────────┤
│  analysis_service.py                                                │
│  - analyze_claim_info()        : 理赔资料分析（qwen-vl-plus）        │
│  - analyze_claim_info_qvq()    : 理赔资料分析（qvq-plus）            │
│  - analyze_policy_info()       : 保单条款分析（qwen-long-latest）    │
│  - analyze_preauth_result()    : 预授权决策生成（qwen3.6-plus）      │
│  - pre_analyze_preauth_result1/2 : 预分析优化                          │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       阿里云 DashScope API                           │
│  - 视觉理解模型（qwen-vl-plus, qvq-plus）                             │
│  - 长文档处理模型（qwen-long-latest）                                 │
│  - 文本生成模型（qwen3.6-plus）                                       │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          数据持久化层                                │
├─────────────────────────────────────────────────────────────────────┤
│  MySQL 数据库                                                       │
│  - claim_case          : 理赔申请主表                                │
│  - basic_info_analysis : 基本信息分析结果                            │
│  - document_analysis   : 理赔资料分析结果                            │
│  - policies_analysis   : 保单条款分析结果                            │
│  - prompt              : 提示词模板配置                               │
│  - gop_config          : 系统配置（除外药品、住院指针等）              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 数据库表结构

### claim_case（理赔申请主表）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| claim_id | VARCHAR | 理赔案件ID（主键） |
| patient_name | VARCHAR | 患者姓名 |
| provider_name | VARCHAR | 医院名称 |
| admission_type | VARCHAR | 入院类型（门诊/住院） |
| admission_date | DATE | 入院日期 |
| pri_diag_desc | VARCHAR | 主要诊断描述 |
| amount | DECIMAL | 预估费用 |
| gop_type | VARCHAR | GOP类型 |
| preauth_status | INT | 预授权状态（0-待处理，1-已完成） |
| preauth_result | TEXT | 预授权结果（JSON格式） |
| basic_info_analyzed | INT | 基本信息分析状态 |
| documents_analyzed | INT | 文档分析状态 |
| policies_analyzed | INT | 保单分析状态 |

### document_analysis（理赔资料分析表）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | INT | 主键 |
| claim_id | VARCHAR | 理赔案件ID |
| file_name | VARCHAR | 文件名 |
| file_url | VARCHAR | 文件URL |
| analysis_result | TEXT | 分析结果 |
| confidence_level | VARCHAR | 置信度 |
| consistency | VARCHAR | 一致性评分 |
| diff | TEXT | OCR差异分析 |
| confirm_status | INT | 确认状态 |

### policies_analysis（保单条款分析表）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | INT | 主键 |
| claim_id | VARCHAR | 理赔案件ID |
| file_name | VARCHAR | 文件名 |
| file_url | VARCHAR | 文件URL |
| policy_type | VARCHAR | 保单类型（tob/product） |
| analysis_result | TEXT | 分析结果 |
| confirm_status | INT | 确认状态 |

### prompt（提示词模板表）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | INT | 主键 |
| prompt_type | VARCHAR | 提示词类型 |
| prompt_type_desc | VARCHAR | 类型描述 |
| prompt | TEXT | 提示词内容 |

---

## API 接口详解

### 1. 初始化预授权 `/api/initPreAuth`

**功能**：从外部系统获取待处理的理赔申请列表，初始化到数据库

**调用时机**：系统启动或定时任务触发

**处理流程**：
```
1. 调用外部API获取理赔申请列表
2. 遍历每个申请，调用 process_claim_init()
3. 检查是否已存在（防止重复处理）
4. 插入 claim_case 表
```

**相关代码位置**：`app.py` 第234-268行

---

### 2. 重新初始化预授权 `/api/initRePreAuth`

**功能**：处理需要重新审核的理赔申请

**调用时机**：需要重新审核时

**处理流程**：
```
1. 调用外部API获取RE理赔申请列表
2. 调用 process_claim_re_init()
3. 重置 claim_case 状态
4. 删除旧的 basic_info_analysis 数据
```

**相关代码位置**：`app.py` 第271-305行

---

### 3. 处理基本信息 `/api/processBasicInfo`

**功能**：获取理赔基本信息和查询数据

**调用时机**：预授权流程第二步

**处理流程**：
```
1. 查询 basic_info_analyzed = 0 的理赔申请
2. 调用 get_claim_info_api() 获取理赔数据
3. 调用 get_expensive_hosp_info_api() 获取昂贵医院信息
4. 调用 get_direct_pay_hosp_api() 获取直付医院信息
5. 插入 basic_info_analysis 表
6. 更新 claim_case.basic_info_analyzed = 1
```

**相关代码位置**：`app.py` 第437-478行

---

### 4. 处理保单条款 `/api/processPoliciesInfo`

**功能**：下载并分析保单条款PDF文档

**调用时机**：预授权流程第三步

**处理流程**：
```
1. 查询 policies_analyzed = 0 的理赔申请
2. 调用 get_policy_wording_url_api() 获取保单URL列表
3. 过滤有效文件（PDF/DOCX/XLSX）
4. 下载文件到本地（OSS URL替换为公网地址）
5. 调用 analyze_policy_info() 分析PDF内容
6. 插入 policies_analysis 表
7. 更新 claim_case.policies_analyzed = 1
```

**使用的模型**：`qwen-long-latest`

**相关代码位置**：`app.py` 第481-570行

---

### 5. 处理理赔资料 `/api/processDocumentsInfo`

**功能**：下载并分析理赔资料图片

**调用时机**：预授权流程第四步

**处理流程**：
```
1. 查询 documents_analyzed = 0 的理赔申请
2. 调用 get_claim_documents_api() 获取文档列表
3. 过滤有效文件（PNG/JPG/JPEG/PDF等）
4. 检查是否已存在分析数据（避免重复处理）
5. 下载图片到本地
6. 调用 download_and_process_image() 转换为base64
7. 调用 analyze_claim_info() 使用qwen-vl-plus分析
8. 调用 analyze_claim_info_qvq() 使用qvq-plus交叉验证
9. 调用 evaluate_image_quality() 评估图片质量
10. 调用 compare_ocr_results() 比较两次OCR结果一致性
11. 插入 document_analysis 表
12. 更新 claim_case.documents_analyzed = 1
```

**使用的模型**：
- `qwen-vl-plus`：主要文档分析
- `qvq-plus-latest`：备用/交叉验证分析

**相关代码位置**：`app.py` 第590-720行

---

### 6. 生成预授权结果 `/api/genPreAuthResult` / `/api/genPreAuthResultMultiThread`

**功能**：综合所有分析结果，生成最终预授权决策

**调用时机**：预授权流程最后一步

**处理流程**：
```
1. 查询已完成三项分析的理赔申请
2. 获取基础信息分析结果
3. 获取理赔资料分析结果，调用 cut_document_info() 精简整理
4. 获取保单条款分析结果
5. 分析住院指针（仅住院类型）：调用 get_inpatient_info()
6. 分析APV信息：调用 get_apv_info()
7. 分析除外治疗/药品：调用 get_except_info()
8. 获取医院信息：调用 HospitalInfo
9. 获取价格知识库：调用 call_dashscope_application()
10. 执行预分析优化（可选）：
    - pre_analyze_preauth_result1()：基于APV信息预判
    - pre_analyze_preauth_result2()：基于综合信息预判
11. 生成最终决策：调用 analyze_preauth_result()
12. 提取结果代码和原因描述
13. 调用外部API更新预授权结果
14. 更新 claim_case 表
```

**使用的模型**：`qwen3.6-plus`

**相关代码位置**：
- `app.py` 第70-229行（process_claim_analysis）
- `app.py` 第308-360行（单线程）
- `app.py` 第362-434行（多线程）

---

## 业务分析函数详解

### analyze_claim_info()

使用视觉语言模型分析医疗票据图片，提取结构化信息。

**输入**：图片URL（base64 data URL）
**输出**：JSON格式的医疗信息提取结果

### analyze_claim_info_qvq()

使用QVQ模型进行二次分析，与主分析交叉验证。

### analyze_preauth_result()

综合分析结果生成最终预授权决策。

**输入参数**：
- basic_info_result：基本信息分析结果
- document_result：医疗文档分析结果
- policy_result_tob：TOB保单条款分析
- policy_result_prod：产品保单条款分析
- gop_type：GOP类型
- price_knowledge_base：价格知识库
- admission_type：入院类型
- prod_type：产品类型
- hospital_info：医院信息
- except_result：除外项目信息
- apv_info：APV信息
- inpatient_info：住院指针信息
- query_details：查询详情
- reco_benfit：推荐福利

**输出格式**：
```json
{
  "result": "01 - 审核通过",
  "reason": "审核通过的原因说明"
}
```

### pre_analyze_preauth_result1()

基于APV信息进行快速预判，优化决策效率。

### pre_analyze_preauth_result2()

基于综合信息进行深度预判，进一步优化决策。

---

## 系统配置

### 环境变量配置 (.env)

| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| DB_HOST | 数据库地址 | localhost |
| DB_PORT | 数据库端口 | 3306 |
| DB_USER | 数据库用户名 | root |
| DB_PASSWORD | 数据库密码 | *** |
| DB_NAME | 数据库名 | gop_db |
| api_key | 阿里云API Key | sk-*** |
| base_url | DashScope API地址 | https://dashscope.aliyuncs.com |
| getGopClaimListUrl | 获取理赔列表API | http://api.xxx.com/claims |
| getClaimInfoApiUrl | 获取理赔详情API | http://api.xxx.com/info |
| getPolicyWordingUrl | 获取保单条款URL | http://api.xxx.com/policy |
| getDocumentsUrl | 获取理赔文档API | http://api.xxx.com/docs |
| updatePreAuthResultUrl | 更新预授权结果API | http://api.xxx.com/update |
| eccsWebUrlBase | ECCS Web API基础地址 | http://eccs-web/ |
| eccsCoreUrlBase | ECCS Core API基础地址 | http://eccs-core/ |

### 模型配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| MODEL_DOCUMENT_ANALYSIS | qwen-vl-plus | 文档分析模型 |
| MODEL_DOCUMENT_QVQ | qqv-plus-latest | QVQ备用模型 |
| MODEL_TEXT_ANALYSIS | qwen3.6-plus | 文本分析模型 |
| MODEL_LONG_DOCUMENT | qwen-long-latest | 长文档处理模型 |
| ENABLE_THINKING | false | 是否启用思考模式 |

### GOP配置表 (gop_config)

系统通过数据库表管理可配置的业务规则：

- `except_medicine`：除外药品列表
- `child_stay_hosp`：儿童住院指针配置
- `adult_stay_hosp`：成人住院指针配置

---

## 系统启动流程

### 定时任务调用顺序

建议按以下顺序定时调用API：

```
1. /api/initPreAuth          # 获取新理赔申请
2. /api/processBasicInfo      # 处理基本信息
3. /api/processPoliciesInfo   # 处理保单条款
4. /api/processDocumentsInfo  # 处理理赔资料
5. /api/genPreAuthResultMultiThread  # 生成审核结果
```

### 启动检查清单

1. ✅ MySQL数据库连接正常
2. ✅ OSS存储桶可访问
3. ✅ 阿里云DashScope API可用
4. ✅ prompt表包含所有必需的提示词模板
5. ✅ gop_config表包含业务规则配置

---

## 图片处理流程

### download_and_process_image()

```
┌─────────────────────────────────────────────────────┐
│  1. 下载图片（带User-Agent头）                       │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│  2. 验证图片大小（>500字节）                          │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│  3. 检测HTML内容（避免下载错误页面）                   │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│  4. 使用PIL验证图片格式                               │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│  5. 转换为RGB模式                                    │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│  6. 重新编码为标准JPEG                               │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│  7. 压缩（如>10MB）                                  │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│  8. 转换为Base64 Data URL                           │
└─────────────────────────────────────────────────────┘
```

---

## 错误处理机制

### 图片格式错误

错误信息：`The image format is illegal and cannot be opened`

可能原因：
1. 下载到的是HTML错误页面而非图片
2. 图片格式不被API支持
3. 图片内容损坏

解决方案：
- 已实现严格的图片验证流程
- 检测并过滤无效图片
- 统一转换为标准JPEG格式

### API限流处理

系统使用OpenAI SDK内置的重试机制处理429错误。

### 线程安全

多线程处理时使用`threading.Lock()`保护共享资源：
- 数据库连接
- 分析结果写入
- 日志输出

---

## 日志查看

日志文件位置：`/app/gop/D:/GopLogs//app.log`

### 关键日志标识

| 日志内容 | 含义 |
|----------|------|
| 开始初始化预授权信息 | 开始处理新的理赔申请 |
| 已存在理赔申请数据，跳过处理 | 避免重复处理 |
| 图片下载完成，大小: X bytes | 图片下载状态 |
| 图片转换为base64完成 | 图片处理成功 |
| 理赔资料分析失败 | 文档分析出错 |
| 保单条款分析失败 | 保单分析出错 |
| Processed claim X successfully | 案件处理成功 |

---

## 项目文件结构

```
/app/gop/
├── app.py                          # Flask应用主文件，API接口定义
├── .env                            # 环境变量配置
├── requirements.txt                # Python依赖
│
├── dao/                            # 数据访问层
│   ├── claim_case_dao.py          # 理赔申请DAO
│   ├── document_analysis_dao.py    # 文档分析DAO
│   ├── policies_analysis_dao.py     # 保单分析DAO
│   ├── basic_info_analyzed_analysis_dao.py  # 基础信息DAO
│   ├── prompt_dao.py               # 提示词DAO
│   ├── gop_config_dao.py           # 系统配置DAO
│   ├── provider_dao.py             # 医疗机构DAO
│   ├── case_pay_dao.py             # 理赔支付DAO
│   ├── expensise_hosp_info_dao.py  # 昂贵医院DAO
│   └── blacklist_member_dao.py     # 黑名单DAO
│
├── llm/                            # LLM服务层
│   ├── analysis_service.py         # 主要分析服务（调用DashScope）
│   ├── analysis_service_agent.py   # Agent模式分析服务
│   └── compare_ocr_results.py     # OCR结果比对
│
├── utils/                         # 工具类
│   ├── image_utils.py              # 图片处理工具
│   ├── image_quality.py            # 图片质量评估
│   ├── file_utils.py               # 文件下载工具
│   ├── api_utils.py                # 外部API调用工具
│   ├── db_utils.py                 # 数据库连接池
│   ├── dao_context.py              # DAO上下文管理
│   ├── hospital_info.py            # 医院信息处理
│   ├── email_utils.py              # 邮件发送工具
│   └── cpt_utils.py                # CPT编码工具
│
├── logger/                         # 日志模块
│   └── logger.py                   # 日志配置
│
└── docs/                           # 文档目录
    └── README.md                   # 项目文档
```

---

## 提示词模板类型

系统使用数据库存储的提示词模板：

| 模板类型 | 用途 |
|----------|------|
| GOP_DOCUMENT | 理赔资料分析提示词 |
| GOP_POLICY | TOB保单条款分析提示词 |
| GOP_POLICY_PROD | 产品保单条款分析提示词 |
| GOP_POLICY_EXTRA | 额外保单条款分析 |
| GOP_PREAUTH | 预授权决策提示词 |
| GOP_INPATIENT | 住院指针分析提示词 |
| GOP_EXCEPT | 除外项目分析提示词 |
| GOP_DIAG_TYPE | 诊断类型分析提示词 |
