# Telegram 频道同步脚本（Bot 版本）

## 说明

这个脚本用于将 Telegram 频道的内容自动同步到博客。

## 配置步骤

### 1. 创建 Telegram Bot

1. 在 Telegram 中搜索 @BotFather
2. 发送 `/newbot` 命令
3. 按照提示输入 Bot 名称和用户名（用户名必须以 bot 结尾）
4. 创建成功后，BotFather 会给您一个 Token，格式类似：`123456789:ABCdefGhIJKlmNoPQRStuVWxyZ`
5. **请妥善保存这个 Token！**

### 2. 将 Bot 添加到频道

1. 打开您要同步的 Telegram 频道
2. 点击频道名称 → 管理员 → 添加管理员
3. 搜索您刚创建的 Bot 并添加
4. 确保 Bot 有"读取消息"的权限

### 3. 配置环境变量

复制 `.env.example` 为 `.env`，并填入您的配置：

```bash
cp .env.example .env
# 编辑 .env 文件，填入您的 Bot Token
```

### 4. 安装依赖

```bash
cd scripts
pip install -r requirements.txt
```

### 5. 测试运行

```bash
python sync_telegram.py
```

### 6. 配置 GitHub Secrets

在 GitHub 仓库的 Settings → Secrets and variables → Actions 中添加以下 secrets：

- `TELEGRAM_BOT_TOKEN`：您的 Bot Token
- `TELEGRAM_CHANNEL`：要同步的频道用户名（不带 @）

### 7. GitHub Actions

工作流文件已创建在 `.github/workflows/sync-telegram.yml`，默认每小时同步一次。

## 注意事项

- ⚠️ **重要**：Telegram Bot API 无法直接获取频道历史消息
- Bot 只能接收频道的**新消息**（需要设置 Webhook 或使用 Long Polling）
- 如果需要同步历史消息，仍需使用 Telegram Client API（需要 api_id 和 api_hash）
- 请妥善保管您的 Bot Token，不要泄露
