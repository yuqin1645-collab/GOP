# GOP系统错误排查与修复清单

## 快速诊断流程图

```
系统启动
   ↓
检查日志 → /app/gop/D:/GopLogs//app.log
   ↓
按错误类型查找对应修复方案
   ↓
应用修复 → 重启服务
```

---

## 常见错误及解决方案

### 错误1：图片处理失败

**日志特征**：
```
PIL处理图片失败: cannot identify image file
图片内容过小，可能是无效图片
```

**原因分析**：
1. 下载到的是HTML错误页面而非图片
2. 图片格式不被PIL支持
3. 图片文件已损坏或不完整

**解决方案**：
✅ **已在 `utils/image_utils.py` 中修复**

新增 `_validate_image_header()` 函数，通过魔数验证图片格式：
- JPEG: `\xff\xd8\xff`
- PNG: `\x89PNG\r\n\x1a\n`
- GIF: `GIF87a` / `GIF89a`
- WEBP: `RIFF`
- BMP: `BM`

同时增强下载验证，检测HTML内容并提前过滤。

**验证方法**：
```bash
# 检查日志中是否仍有PIL错误
grep "PIL处理图片失败" /app/gop/D:/GopLogs//app.log | tail -20
```

---

### 错误2：API请求参数错误

**日志特征**：
```
Missing required parameter: 'messages.[0].content[1].image_url.url'
You provided 'urls', did you mean to provide 'url'?
```

**原因分析**：
- 直接调用 `client.chat.completions.create()` 而不是通过统一的 `create_chat_completion()` 函数
- 消息格式不符合OpenAI API规范

**解决方案**：
✅ **已在 `llm/analysis_service.py` 中修复**

修改的函数：
- `analyze_news`() - 第149-220行
- `analyze_claim_info_qvq()` - 第223-267行

统一使用 `create_chat_completion()` 函数，该函数会自动处理参数和异常。

**验证方法**：
```bash
# 检查是否还有400错误
grep "Missing required parameter" /app/gop/D:/GopLogs//app.log | tail -20
```

---

### 错误3：文件上传失败

**日志特征**：
```
'file' is a required property.
```

**原因分析**：
- OpenAI SDK的 `files.create()` 方法参数传递方式不正确
- 文件对象未正确包装

**解决方案**：
✅ **已在 `llm/analysis_service.py` 中修复**

修改的函数：
- `analyze_policy_info()` - 第267-289行
- `analyze_policy_extra_info()` - 第292-311行
- `analyze_document_pdf_info()` - 第338-357行

增强内容：
1. 文件存在性验证
2. 文件大小检查（防止空文件）
3. 详细的错误日志
4. 确保finally块中删除文件

**验证方法**：
```bash
# 检查文件上传错误
grep "file.*is a required property" /app/gop/D:/GopLogs//app.log | tail -20
```

---

### 错误4：文件加密或损坏

**日志特征**：
```
File [id:file-xxx] content is encrypted or corrupted.
```

**原因分析**：
1. PDF文件本身已加密
2. 下载不完整或网络错误
3. 文件在传输过程中损坏

**解决方案**：

**临时处理**（代码已包含）：
- 捕获异常并返回 `None`
- 记录详细错误日志
- 继续处理其他文件

**长期处理**：
1. 检查OSS下载链接是否有效
2. 验证文件完整性（MD5校验）
3. 过滤已知的加密文件

**验证方法**：
```bash
# 检查加密文件错误
grep "encrypted or corrupted" /app/gop/D:/GopLogs//app.log
```

---

### 错误5：API频率限制

**日志特征**：
```
Error code: 429 - You have exceeded your current request limit
```

**原因分析**：
- 多线程并发请求过多（20个线程）
- DashScope API有速率限制
- 短时���内大量图片分析请求

**解决方案**：

**短期缓解**：
1. 减少线程池大小（当前20 → 建议5-10）
   ```python
   max_workers = 10  # 在 app.py 中调整
   ```

2. 添加请求延迟（在图片处理循环中）
   ```python
   import time
   time.sleep(0.5)  # 每次请求间隔0.5秒
   ```

3. 监控API配额使用情况

**长期方案**：
1. 实现请求队列和速率限制器
2. 添加重试机制（已内置，会自动重试）
3. 考虑使用批处理模式

**验证方法**：
```bash
# 检查429错误频率
grep "429 Too Many Requests" /app/gop/D:/GopLogs//app.log | wc -l
```

---

### 错误6：数据库连接问题

**日志特征**：
```
Error getting connection from pool
MySQL server has gone away
```

**解决方案**：
1. 检查数据库连接配置（`.env`文件）
2. 验证数据库服务是否运行
3. 调整连接池大小（`db_utils.py`中 `maxconnections=10`）

---

## 系统重启检查清单

### 预启动检查

- [ ] MySQL数据库运行正常
- [ ] 数据库连接配置正确（`.env`文件）
- [ ] DashScope API密钥有效
- [ ] API配额充足
- [ ] OSS存储桶可访问
- [ ] prompt表包含必需的提示词
- [ ] gop_config表包含业务规则配置

### 启动步骤

```bash
# 1. 进入项目目录
cd /app/gop

# 2. 激活虚拟环境（如有）
source myenv/bin/activate

# 3. 检查环境变量
cat .env

# 4. 启动Flask服务
python app.py

# 或使用gunicorn（生产环境）
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### 验证服务运行

```bash
# 检查服务是否运行
ps aux | grep python

# 查看实时日志
tail -f /app/gop/D:/GopLogs//app.log

# 测试API接口
curl -X POST http://localhost:5000/api/health
```

---

## 日志监控关键指标

### 关键日志模式

| 模式 | 含义 | 优先级 |
|------|------|--------|
| `ERROR` | 严重错误，需要立即处理 | 🔴 高 |
| `WARNING` | 警告，需要注意 | 🟡 中 |
| `图片下载完成` | 正常流程 | 🟢 低 |
| `Processed claim` | 案件处理成功 | 🟢 低 |
| `已存在...跳过处理` | 正常去重 | 🟢 低 |

### 实时监控命令

```bash
# 监控错误数量
tail -f /app/gop/D:/GopLogs//app.log | grep --line-buffered "ERROR" | tee error.log

# 统计最近1小时错误
awk -F'|' '/ERROR/ && $1 > "'$(date -d '1 hour ago' '+%Y-%m-%d %H:%M:%S')'"' \
  /app/gop/D:/GopLogs//app.log | wc -l

# 查看失败案件ID
grep "理赔资料分析失败" /app/gop/D:/GopLogs//app.log | \
  grep -oP ' \K\d+' | sort | uniq
```

---

## 数据库状态检查

### 检查未完成的案件

```sql
-- 查询待处理的理赔申请
SELECT claim_id, preauth_status, basic_info_analyzed, documents_analyzed, policies_analyzed
FROM claim_case
WHERE preauth_status = 0
ORDER BY transmission_date DESC
LIMIT 20;

-- 查询分析失败的案件
SELECT claim_id, preauth_result, ai_reason
FROM claim_case
WHERE preauth_status = 1 AND (preauth_result LIKE '%error%' OR preauth_result IS NULL)
LIMIT 20;

-- 统计各状态案件数量
SELECT
    COUNT(*) as total,
    SUM(CASE WHEN basic_info_analyzed = 0 THEN 1 ELSE 0 END) as pending_basic,
    SUM(CASE WHEN documents_analyzed = 0 THEN 1 ELSE 0 END) as pending_documents,
    SUM(CASE WHEN policies_analyzed = 0 THEN 1 ELSE 0 END) as pending_policies,
    SUM(CASE WHEN preauth_status = 0 THEN 1 ELSE 0 END) as pending_final
FROM claim_case;
```

### 清理重复数据

```sql
-- 查看重复的document_analysis记录
SELECT claim_id, file_name, COUNT(*) as cnt
FROM document_analysis
GROUP BY claim_id, file_name
HAVING cnt > 1;

-- 删除重复记录（保留最新的一条）
DELETE da1 FROM document_analysis da1
INNER JOIN document_analysis da2
WHERE
    da1.id < da2.id
    AND da1.claim_id = da2.claim_id
    AND da1.file_name = da2.file_name;
```

---

## API调用顺序（重要！）

系统处理流程必须按顺序调用API：

```
第1步：POST /api/initPreAuth
       ↓ 初始化理赔申请
第2步：POST /api/processBasicInfo
       ↓ 获取基本信息
第3步：POST /api/processPoliciesInfo
       ↓ 分析保单条款
第4步：POST /api/processDocumentsInfo
       ↓ 分析理赔资料
第5步：POST /api/genPreAuthResultMultiThread
       ↓ 生成最终审核结果
```

**错误顺序的后果**：
- 先调用第4步 → 缺少数据 → 分析失败
- 跳过第2步 → 缺少基础信息 → 第5步失败

---

## 提示词模板检查

系统依赖数据库中的提示词模板，缺失会导致分析失败。

### 必需提示词类型

```sql
-- 检查所有必需的提示词
SELECT prompt_type, prompt_type_desc, LENGTH(prompt) as length
FROM prompt
WHERE prompt_type IN (
    'GOP_DOCUMENT',        -- 理赔资料分析
    'GOP_POLICY',          -- TOB保单分析
    'GOP_POLICY_PROD',     -- 产品保单分析
    'GOP_POLICY_EXTRA',    -- 额外保单分析
    'GOP_PREAUTH',         -- 预授权决策
    'GOP_INPATIENT',       -- 住院指针
    'GOP_EXCEPT',          -- 除外项目
    'GOP_DIAG_TYPE'        -- 诊断类型
);
```

### 缺失提示词的补救

如果提示词缺失，可以从备份恢复或手动插入：

```sql
-- 示例：插入GOP_DOCUMENT提示词
INSERT INTO prompt (prompt_type, prompt_type_desc, prompt) VALUES (
    'GOP_DOCUMENT',
    '理赔资料分析提示词',
    '## 角色与任务...（完整的提示词内容）'
);
```

---

## 配置文件检查

### .env 文件必需变量

```bash
# 数据库配置
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=***
DB_NAME=gop_db

# DashScope API配置
api_key=sk-***
base_url=https://dashscope.aliyuncs.com

# 外部API地址
getGopClaimListUrl=http://...
getClaimInfoApiUrl=http://...
getPolicyWordingUrl=http://...
getDocumentsUrl=http://...
updatePreAuthResultUrl=http://...

# ECCS API
eccsWebUrlBase=http://eccs-web/
eccsCoreUrlBase=http://eccs-core/

# 模型配置（可选，有默认值）
MODEL_DOCUMENT_ANALYSIS=qwen-vl-plus
MODEL_DOCUMENT_QVQ=qvq-plus-latest
MODEL_TEXT_ANALYSIS=qwen3.5-plus
MODEL_LONG_DOCUMENT=qwen-long-latest
ENABLE_THINKING=false
```

---

## 性能优化建议

### 当前配置
- 线程池大小：20
- 数据库连接池：10
- 图片最大尺寸：10MB

### 推荐调整

```python
# app.py 中调整
max_workers = 10  # 减少并发，避免API限流

# db_utils.py 中调整
maxconnections=20  # 增加数据库连接池

# image_utils.py 中调整
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 降低到5MB，减少传输时间
```

---

## 故障恢复流程

### 场景1：部分案件处理失败

**症状**：日志中大量 `理赔资料分析失败` 警告

**恢复步骤**：
1. 查询失败案件ID
   ```sql
   SELECT claim_id FROM claim_case WHERE preauth_status = 0 AND documents_analyzed = 1;
   ```

2. 清理失败案件的分析数据
   ```sql
   DELETE FROM document_analysis WHERE claim_id = '失败的claim_id';
   UPDATE claim_case SET documents_analyzed = 0 WHERE claim_id = '失败的claim_id';
   ```

3. 重新执行 `/api/processDocumentsInfo`

### 场景2：API配额用尽

**症状**：大量 `429 Too Many Requests` 错误

**恢复步骤**：
1. 立即停止所有处理进程
2. 等待API配额恢复（通常1小时后）
3. 降低并发数（max_workers=5）
4. 重新启动服务

### 场景3：数据库连接池耗尽

**症状**：`Error getting connection from pool`

**恢复步骤**：
1. 检查是否有死锁连接
   ```sql
   SHOW PROCESSLIST;
   ```

2. 杀掉长时间空闲的连接
   ```sql
   KILL <thread_id>;
   ```

3. 重启应用服务

---

## 重要文件位置

| 文件 | 路径 | 用途 |
|------|------|------|
| 主程序 | `/app/gop/app.py` | Flask API服务 |
| LLM服务 | `/app/gop/llm/analysis_service.py` | AI模型调用 |
| 图片工具 | `/app/gop/utils/image_utils.py` | 图片下载处理 |
| 数据库工具 | `/app/gop/utils/db_utils.py` | 连接池管理 |
| DAO层 | `/app/gop/dao/*.py` | 数据访问对象 |
| 日志文件 | `/app/gop/D:/GopLogs//app.log` | 系统运行日志 |
| 配置文件 | `/app/gop/.env` | 环境变量 |
| 文档 | `/app/gop/docs/` | 项目文档 |

---

## 联系支持

如果以上方案无法解决问题：

1. 收集日志：
   ```bash
   # 导出最近1000行错误日志
   grep -E "ERROR|WARNING" /app/gop/D:/GopLogs//app.log | tail -1000 > /tmp/error_log.txt
   ```

2. 收集系统信息：
   ```bash
   # 系统信息
   uname -a > /tmp/system_info.txt
   # Python版本
   python --version >> /tmp/system_info.txt
   # 包列表
   pip freeze > /tmp/requirements.txt
   ```

3. 联系开发团队，提供以上文件
