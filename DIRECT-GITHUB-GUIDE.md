# 📱 直接发布到 GitHub 指南

不经过Telegram，直接写博客并提交到GitHub！

---

## 🎯 方案一：使用 GitHub App（最简单）

### 步骤：

1. **下载 GitHub App**
   - 在 App Store 搜索「GitHub」
   - 下载并安装官方 GitHub App

2. **登录您的账号**
   - 使用您的 GitHub 账号登录

3. **创建新博客文章**
   - 打开仓库：`lionel518/imperial-blog`
   - 进入 `src/content/blog/` 目录
   - 点击右上角「+」→ 「Create new file」

4. **编写博客**
   - 文件名：使用日期+标题，例如 `2026-03-25-my-blog-post.md`
   - 内容格式（见下方）

5. **提交更改**
   - 点击「Commit changes」
   - 输入提交信息：`feat: add new blog post`
   - 点击「Commit changes」

6. **等待自动部署**
   - Cloudflare Pages 会自动部署
   - 1-3 分钟后博客就更新了！

---

## 📝 博客文章格式

**必须包含 Frontmatter（前三行）：**

```markdown
---
title: "博客标题"
pubDatetime: 2026-03-25T21:00:00+08:00
description: "博客描述"
tags: ["标签1", "标签2"]
heroImage: "/assets/blog/xxx.jpg"
draft: false
---

博客内容从这里开始...

可以使用 Markdown 格式：
- **粗体**
- *斜体*
- `代码`

## 标题

正文内容...
```

---

## 🎯 方案二：创建 iOS 快捷指令（高级）

通过快捷指令直接调用 GitHub API 创建博客文章！

### 前置准备：

1. **创建 GitHub Personal Access Token**
   - 访问：https://github.com/settings/tokens
   - 点击「Generate new token」→「Generate new token (classic)」
   - 勾选 `repo` 权限
   - 生成并保存 token（只显示一次！）

2. **在快捷指令中保存 Token**
   - 打开「快捷指令」App
   - 创建一个新快捷指令
   - 添加操作：「文本」→ 输入您的 Token
   - 添加操作：「设置变量」→ 命名为 `GitHubToken`

---

## 🛠️ 快捷指令创建步骤

### 第一步：创建新快捷指令

1. 打开「快捷指令」App
2. 点击右上角「+」
3. 命名为「发布博客」

### 第二步：询问博客标题

1. 点击「添加操作」
2. 搜索「询问输入」
3. 选择「询问输入」
4. 设置：
   - 提示：「请输入博客标题」
   - 输入类型：文本

### 第三步：询问博客内容

1. 点击「添加操作」
2. 搜索「询问输入」
3. 选择「询问输入」
4. 设置：
   - 提示：「请输入博客内容」
   - 输入类型：文本
   - 勾选「允许换行」

### 第四步：询问标签

1. 点击「添加操作」
2. 搜索「询问输入」
3. 选择「询问输入」
4. 设置：
   - 提示：「请输入标签（用逗号分隔）」
   - 输入类型：文本
   - 默认：「生活,思考」

### 第五步：生成文件名

1. 点击「添加操作」
2. 搜索「日期」
3. 选择「获取当前日期」
4. 点击「添加操作」
5. 搜索「格式化日期」
6. 选择「格式化日期」
7. 设置格式：`yyyy-MM-dd`
8. 点击「添加操作」
9. 搜索「文本」
10. 选择「文本」
11. 输入：`[格式化的日期]-[标题].md`
12. 添加操作：「替换文本」
    - 查找：「 」（空格）
    - 替换：「-」
13. 添加操作：「设置变量」→ 命名为 `filename`

### 第六步：生成 Frontmatter

1. 点击「添加操作」
2. 搜索「日期」
3. 选择「获取当前日期」
4. 点击「添加操作」
5. 搜索「格式化日期」
6. 选择「格式化日期」
7. 设置格式：`ISO 8601`
8. 点击「添加操作」
9. 搜索「文本」
10. 选择「文本」
11. 输入：
    ```
    ---
    title: "[询问标题的结果]"
    pubDatetime: [ISO 8601 日期]
    description: "[询问标题的结果]"
    tags: [[询问标签的结果]]
    ---

    [询问内容的结果]
    ```
12. 添加操作：「设置变量」→ 命名为 `content`

### 第七步：调用 GitHub API

这部分比较复杂，建议使用「通过 SSH 运行脚本」或「运行 JavaScript」操作。

**简化方案：**
使用 GitHub App 反而更简单！

---

## 🎯 方案三：使用 Working Copy App（推荐）

Working Copy 是一个强大的 iOS Git 客户端！

### 步骤：

1. **下载 Working Copy**
   - App Store 搜索「Working Copy」
   - 下载并安装

2. **克隆仓库**
   - 点击「+」→「Clone Repository」
   - 输入：`https://github.com/lionel518/imperial-blog.git`
   - 选择保存位置

3. **创建新博客**
   - 进入 `src/content/blog/` 目录
   - 点击「+」→「New File」
   - 输入文件名：`2026-03-25-title.md`
   - 编写内容（使用 Markdown 格式）

4. **提交并推送**
   - 点击「Repository」→「Commit」
   - 输入提交信息
   - 点击「Commit」
   - 点击「Push」

---

## 💡 臣的推荐

**最简单：使用 GitHub App**
- 无需配置
- 官方应用，稳定可靠
- 界面友好

**最强大：使用 Working Copy**
- 完整的 Git 功能
- 可以离线编辑
- 支持分支、合并等高级功能

**不推荐：自己写快捷指令**
- 配置复杂
- 需要处理 API 认证
- 容易出错

---

## 📋 快速开始（GitHub App）

1. 下载 GitHub App
2. 登录您的账号
3. 进入 `lionel518/imperial-blog` 仓库
4. 在 `src/content/blog/` 目录创建新文件
5. 按照格式编写博客
6. 提交更改
7. 等待 Cloudflare Pages 自动部署

就这么简单！🎉

需要臣帮您做其他事情吗？📜
