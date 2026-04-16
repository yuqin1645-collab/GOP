# GOP系统重启快速检查清单

## 📋 重启前准备（5分钟）

### 1. 检查依赖服务状态

```bash
# 检查MySQL数据库
systemctl status mysqld  # 或 mysql
# 或直接测试连接
mysql -h $DB_HOST -P $DB_PORT -u $DB_USER -p$DB_NAME -e "SELECT 1;"

# 检查网络连通性
curl -I http://your-external-api-endpoint
curl -I https://dashscope.aliyuncs.com
```

### 2. 验证配置文件

```bash
cd /app/gop
# 检查.env文件是否存在且完整
cat .env | grep -v "^#" | grep "="

# 必需变量检查清单：
# DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
# api_key, base_url
# getGopClaimListUrl, getClaimInfoApiUrl, getPolicyWordingUrl
# getDocumentsUrl, updatePreAuthResultUrl
```

### 3. 检查磁盘空间

```bash
# 检查下载目录
df -h /app/gop/downloads

# 清理旧文件（如有需要）
rm -rf /app/gop/downloads/*
```

### 4. 查看上次运行状态

```bash
# 查看最近的错误
tail -100 /app/gop/D:/GopLogs//app.log | grep -E "ERROR|WARNING"

# 查看是否有未完成的claim
mysql -e "SELECT COUNT(*) as pending FROM claim_case WHERE preauth_status=0"
```

---

## 🚀 启动步骤（按顺序执行）

### Step 1: 启动Flask服务

```bash
cd /app/gop

# 方式1：直接运行（开发环境）
python app.py

# 方式2：使用gunicorn（生产环境）
gunicorn -w 4 -b 0.0.0.0:5000 app:app --daemon

# 方式3：使用supervisor（推荐）
# 编辑 /etc/supervisor/conf.d/gop.conf
# 然后执行：
supervisorctl reread
supervisorctl update
supervisorctl start gop
```

**验证服务启动**：
```bash
# 检查进程
ps aux | grep -E "python|gunicorn" | grep -v grep

# 检查端口
netstat -tlnp | grep :5000

# 测试健康检查接口（如有）
curl http://localhost:5000/
```

### Step 2: 监控启动日志

```bash
# 实时监控日志（另开一个终端）
tail -f /app/gop/D:/GopLogs//app.log

# 重点关注以下关键词：
# - "Flask app starting up"
# - "开始处理" (表示API被调用)
# - "ERROR" (错误)
# - "Successfully" (成功)
```

---

## 🔄 标准处理流程调用顺序

**重要：必须按以下顺序手动触发或配置定时任务！**

```bash
# 方式1：curl命令手动触发

# 第1步：获取新理赔申请
curl -X POST http://localhost:5000/api/initPreAuth

# 第2步：处理基本信息（等待第1步完成后再执行）
curl -X POST http://localhost:5000/api/processBasicInfo

# 第3步：处理保单条款
curl -X POST http://localhost:5000/api/processPoliciesInfo

# 第4步：处理理赔资料
curl -X POST http://localhost:5000/api/processDocumentsInfo

# 第5步：生成预授权结果
curl -X POST http://localhost:5000/api/genPreAuthResultMultiThread
```

```bash
# 方式2：使用crontab定时任务（推荐）

# 编辑crontab
crontab -e

# 添加以下内容（每30分钟执行一次完整流程）
*/30 * * * * /usr/bin/curl -X POST http://localhost:5000/api/initPreAuth >> /var/log/gop/cron.log 2>&1
*/30 * * * * sleep 5 && /usr/bin/curl -X POST http://localhost:5000/api/processBasicInfo >> /var/log/gop/cron.log 2>&1
*/30 * * * * sleep 10 && /usr/bin/curl -X POST http://localhost:5000/api/processPoliciesInfo >> /var/log/gop/cron.log 2>&1
*/30 * * * * sleep 15 && /usr/bin/curl -X POST http://localhost:5000/api/processDocumentsInfo >> /var/log/gop/cron.log 2>&1
*/30 * * * * sleep 20 && /usr/bin/curl -X POST http://localhost:5000/api/genPreAuthResultMultiThread >> /var/log/gop/cron.log 2>&1
```

**注意**：如果某个步骤失败，后续步骤可能无法正常执行，需要先修复问题。

---

## 🔍 重启后验证（10分钟）

### 1. 检查API调用记录

```bash
# 查看最近API调用
tail -50 /app/gop/D:/GopLogs//app.log | grep "开始处理"

# 应该看到类似这样的日志：
# 开始处理 5 个理赔申请
# 开始处理 5 个理赔申请的基本信息
# 开始处理 5 个理赔申请的保单条款分析
# ...
```

### 2. 检查数据库状态

```sql
-- 连接数据库
mysql -h $DB_HOST -P $DB_PORT -u $DB_USER -p$DB_NAME

-- 查看新增的claim数量
SELECT COUNT(*) as total_claims FROM claim_case
WHERE create_time > DATE_SUB(NOW(), INTERVAL 10 MINUTE);

-- 查看完成进度
SELECT
    COUNT(*) as total,
    SUM(CASE WHEN basic_info_analyzed = 1 THEN 1 ELSE 0 END) as basic_done,
    SUM(CASE WHEN documents_analyzed = 1 THEN 1 ELSE 0 END) as documents_done,
    SUM(CASE WHEN policies_analyzed = 1 THEN 1 ELSE 0 END) as policies_done,
    SUM(CASE WHEN preauth_status = 1 THEN 1 ELSE 0 END) as completed
FROM claim_case
WHERE create_time > DATE_SUB(NOW(), INTERVAL 10 MINUTE);
```

### 3. 检查异常

```bash
# 查看错误数量
ERROR_COUNT=$(grep -c "ERROR" /app/gop/D:/GopLogs//app.log)
echo "最近错误数: $ERROR_COUNT"

# 如果错误数 > 50，需要调查原因
if [ $ERROR_COUNT -gt 50 ]; then
    echo "警告：错误数量异常，请检查日志！"
    tail -100 /app/gop/D:/GopLogs//app.log | grep "ERROR"
fi
```

---

## ⚠️ 常见重启后问题

### 问题1：API调用顺序错乱

**症状**：`processDocumentsInfo` 报错 "无法获取理赔资料链接"

**原因**：`initPreAuth` 还未完成就执行了后续步骤

**解决**：
```bash
# 1. 停止所有定时任务
crontab -e  # 注释掉所有任务

# 2. 重新按顺序执行
curl -X POST http://localhost:5000/api/initPreAuth
# 等待30秒，确认完成后再继续
sleep 30
curl -X POST http://localhost:5000/api/processBasicInfo
# ...
```

### 问题2：API配额用尽

**症状**：大量 `429 Too Many Requests` 错误

**解决**：
1. 立即停止服务
2. 等待1小时让配额恢复
3. 修改配置降低并发：
   ```python
   # app.py 第408行
   max_workers = 5  # 从20改为5
   ```
4. 重新启动

### 问题3：数据库连接失败

**症状**：`Error getting connection from pool`

**解决**：
```bash
# 检查数据库是否运行
systemctl status mysqld

# 重启数据库
systemctl restart mysqld

# 检查连接数
mysql -e "SHOW PROCESSLIST;"

# 杀死死连接
mysql -e "KILL <thread_id>;"
```

### 问题4：图片处理全部失败

**症状**：`PIL处理图片失败` 大量出现

**解决**：
1. 检查代码版本是否包含 `_validate_image_header` 函数
   ```bash
   grep -n "_validate_image_header" /app/gop/utils/image_utils.py
   ```
   如果不存在，说明未修复，需要更新代码

2. 清理图片缓存并重试
   ```bash
   rm -rf /app/gop/downloads/*
   ```

3. 查看具体错误类型：
   ```bash
   tail -200 /app/gop/D:/GopLogs//app.log | grep "PIL处理图片失败"
   ```

---

## 📊 监控仪表板命令

将以下命令保存为 `/app/gop/monitor.sh` 并设置为每5分钟执行：

```bash
#!/bin/bash
LOG_FILE="/app/gop/D:/GopLogs//app.log"
DB_HOST="localhost"
DB_USER="root"
DB_PASS="***"
DB_NAME="gop_db"

echo "=== GOP系统状态监控 ==="
echo "时间: $(date)"
echo ""

# 1. 服务状态
echo "1. 服务状态:"
if pgrep -f "gunicorn" > /dev/null || pgrep -f "python app.py" > /dev/null; then
    echo "   ✅ Flask服务运行中"
else
    echo "   ❌ Flask服务未运行！"
fi
echo ""

# 2. 最近错误数
echo "2. 最近100行错误数:"
tail -100 $LOG_FILE | grep -c "ERROR" || echo "   0"
echo ""

# 3. 待处理案件
echo "3. 数据库待处理案件:"
mysql -h $DB_HOST -u $DB_USER -p$DB_PASS $DB_NAME -N -e \
    "SELECT COUNT(*) FROM claim_case WHERE preauth_status = 0;" 2>/dev/null || echo "   查询失败"
echo ""

# 4. 最近1小时处理量
echo "4. 最近1小时完成案件数:"
mysql -h $DB_HOST -u $DB_USER -p$DB_PASS $DB_NAME -N -e \
    "SELECT COUNT(*) FROM claim_case WHERE preauth_status = 1 AND update_time > DATE_SUB(NOW(), INTERVAL 1 HOUR);" 2>/dev/null || echo "   查询失败"
echo ""

# 5. API配额（如果可用）
echo "5. 磁盘空间:"
df -h /app/gop | tail -1
echo ""
```

**使用**：
```bash
chmod +x /app/gop/monitor.sh
./monitor.sh
```

---

## 🆘 紧急恢复流程

如果系统完全崩溃或无法启动：

### 第1步：立即停止所有进程

```bash
# 停止Flask服务
pkill -f "python app.py"
pkill -f "gunicorn"

# 停止定时任务
crontab -e  # 注释掉所有任务
```

### 第2步：收集诊断信息

```bash
cd /app/gop

# 收集日志
cp /app/gop/D:/GopLogs//app.log /tmp/app.log.bak

# 收集系统信息
uname -a > /tmp/system.txt
free -h >> /tmp/system.txt
df -h >> /tmp/system.txt

# 收集Python环境
pip freeze > /tmp/requirements.txt

# 收集最近错误
tail -500 /app/gop/D:/GopLogs//app.log | grep "ERROR" > /tmp/errors.txt
```

### 第3步：检查并修复数据

```bash
# 连接数据库检查
mysql -h $DB_HOST -u $DB_USER -p$DB_PASSWORD $DB_NAME

# 查看是否有未完成的不一致状态
SELECT claim_id, basic_info_analyzed, documents_analyzed, policies_analyzed, preauth_status
FROM claim_case
WHERE preauth_status = 0
  AND (basic_info_analyzed = 1 OR documents_analyzed = 1 OR policies_analyzed = 1)
LIMIT 10;
```

### 第4步：重新部署代码

```bash
# 如果代码有更新，拉取最新版本
cd /app/gop
git pull origin main

# 重新安装依赖（如有更新）
pip install -r requirements.txt

# 重新启动服务
gunicorn -w 4 -b 0.0.0.0:5000 app:app --daemon
```

### 第5步：逐步验证

```bash
# 1. 测试单个API
curl -X POST http://localhost:5000/api/initPreAuth

# 2. 等待10秒
sleep 10

# 3. 查看日志确认
tail -20 /app/gop/D:/GopLogs//app.log

# 4. 如果正常，逐步执行后续步骤（见上文）
```

---

## 📞 紧急联系人

| 问题类型 | 负责人 | 联系方式 |
|----------|--------|----------|
| 数据库问题 | DBA团队 | @DBA |
| API接口问题 | 后端开发 | @Backend |
| AI模型问题 | AI团队 | @AI_Team |
| 部署问题 | 运维团队 | @Ops |

---

## 📝 重启记录模板

每次重启后填写此表格：

| 项目 | 内容 |
|------|------|
| 重启时间 | 2026-04-16 HH:MM |
| 重启原因 | 正常维护 / 故障修复 / 版本更新 |
| 涉及版本 | commit hash或版本号 |
| 执行人 | @姓名 |
| 检查项 | ✅ 所有检查项通过 |
| 首次API调用时间 | HH:MM:SS |
| 首次成功处理案件 | claim_id: XXX |
| 备注 | 特殊情况说明 |

**保存位置**：`/app/gop/docs/restart_logs/YYYY-MM-DD_HH-MM.md`

---

## 🎯 快速命令参考卡

```bash
# 查看实时日志
tail -f /app/gop/D:/GopLogs//app.log

# 查看最近错误
grep "ERROR" /app/gop/D:/GopLogs//app.log | tail -50

# 重启服务
supervisorctl restart gop

# 查看服务状态
supervisorctl status gop

# 测试API
curl -X POST http://localhost:5000/api/initPreAuth -v

# 查看数据库连接数
mysql -e "SHOW STATUS LIKE 'Threads_connected';"

# 清理下载目录
rm -rf /app/gop/downloads/*

# 备份日志
cp /app/gop/D:/GopLogs//app.log /backup/app_$(date +%Y%m%d_%H%M%S).log
```

---

## ✅ 重启成功确认清单

重启完成后，确认以下所有项目：

- [ ] Flask服务进程正在运行
- [ ] 端口5000可以访问
- [ ] 日志中没有启动错误
- [ ] 第1个API调用成功并返回200
- [ ] 数据库中新增了claim_case记录
- [ ] basic_info_analyzed字段更新为1
- [ ] documents_analyzed字段更新为1
- [ ] policies_analyzed字段更新为1
- [ ] preauth_status更新为1
- [ ] 外部API回调成功（updatePreAuthResultUrl）
- [ ] 连续10分钟没有ERROR级别日志

全部确认完成后，重启流程结束！🎉
