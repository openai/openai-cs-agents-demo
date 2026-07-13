# PostgreSQL 备份与恢复 Runbook

## 1. 备份

生产环境通过密钥管理服务注入 `DATABASE_URL`，执行：

```bash
BACKUP_DIR=/secure/backups deploy/scripts/backup_postgres.sh
```

备份脚本生成 PostgreSQL custom-format 文件及 SHA-256 校验文件。备份目录必须位于加密存储，且不得提交到代码仓库。

## 2. 恢复演练

恢复只能针对已确认的空白演练数据库：

```bash
RESTORE_DATABASE_URL=postgresql://... \
BACKUP_PATH=/secure/backups/enterprise-agent-YYYYMMDDTHHMMSSZ.dump \
CONFIRM_RESTORE=YES \
deploy/scripts/restore_postgres.sh
```

脚本会先验证 SHA-256，再清理并恢复目标数据库。不得把生产数据库 URL 用作演练目标。

## 3. 恢复验收

1. 核对线程、消息、知识、草稿、审计和 Trace 数量。
2. 抽查租户隔离、草稿解密、引用版本和成员状态。
3. 运行后端测试、关键浏览器流程和 P0 红队集。
4. 记录备份时间、恢复开始/结束时间、实际 RPO/RTO 和异常。

内部试点目标为 `RPO <= 24 小时`、`RTO <= 4 小时`。完成真实演练前不得标记为已达标。
