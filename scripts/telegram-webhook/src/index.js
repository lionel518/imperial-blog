/**
 * Telegram → GitHub Actions Webhook Worker
 *
 * 接收 Telegram Bot 的 webhook 推送，
 * 通过 GitHub API 触发 sync-telegram.yml workflow_dispatch，
 * 由 GitHub Actions 完成实际的同步工作（更稳定、可重试、有日志）。
 *
 * 环境变量（通过 `wrangler secret put` 设置）：
 *   TELEGRAM_BOT_TOKEN: Bot API Token
 *   GITHUB_TOKEN: GitHub Personal Access Token (with repo scope)
 */

const GITHUB_API = 'https://api.github.com';
const REPO = 'lionel518/imperial-blog';

export default {
  async fetch(request, env, ctx) {
    // 健康检查端点
    if (request.method === 'GET') {
      return new Response(JSON.stringify({
        status: 'ok',
        worker: 'telegram-blog-sync',
        mode: 'workflow-dispatch',
        hasBotToken: !!env.TELEGRAM_BOT_TOKEN,
        hasGitHubToken: !!env.GITHUB_TOKEN
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    if (request.method !== 'POST') {
      return new Response('Method Not Allowed', { status: 405 });
    }

    try {
      const update = await request.json();

      // 忽略非消息类更新
      if (!update.message && !update.channel_post) {
        return new Response('OK', { status: 200 });
      }

      const msg = update.message || update.channel_post;
      const msgId = msg.message_id;
      const text = msg.caption || msg.text || '';
      const photo = msg.photo;

      // 跳过带按钮的消息（广告、投票等）
      if (msg.reply_markup?.inline_keyboard?.length > 0) {
        return new Response('OK (has buttons, skipped)', { status: 200 });
      }

      // 跳过纯文字消息（只发文字不带图片的不算正式帖子）
      if (text && !photo) {
        return new Response('OK (text-only, skipped)', { status: 200 });
      }

      // 跳过空消息
      if (!text && !photo) {
        return new Response('OK', { status: 200 });
      }

      // 检查必要配置
      if (!env.GITHUB_TOKEN) {
        return new Response(JSON.stringify({ error: 'Missing GITHUB_TOKEN' }), {
          status: 500,
          headers: { 'Content-Type': 'application/json' }
        });
      }

      // 通过 GitHub API 触发 workflow_dispatch
      // workflow 文件名: sync-telegram.yml
      const workflowPath = '.github/workflows/sync-telegram.yml';
      const dispatchUrl = `${GITHUB_API}/repos/${REPO}/actions/workflows/${workflowPath}/dispatches`;

      const payload = {
        ref: 'main',
        inputs: {
          // 传递当前 message_id，让 workflow 从这个 ID 开始同步
          message_id: { value: String(msgId) }
        }
      };

      const resp = await fetch(dispatchUrl, {
        method: 'POST',
        headers: {
          'Authorization': `token ${env.GITHUB_TOKEN}`,
          'Accept': 'application/vnd.github.v3+json',
          'Content-Type': 'application/json',
          'User-Agent': 'telegram-blog-sync-worker/1.0'
        },
        body: JSON.stringify(payload)
      });

      if (!resp.ok) {
        const err = await resp.text();
        console.error(`Workflow dispatch failed: ${resp.status} ${err}`);
        return new Response(JSON.stringify({ error: `Dispatch failed: ${resp.status}`, detail: err }), {
          status: 502,
          headers: { 'Content-Type': 'application/json' }
        });
      }

      console.log(`Triggered workflow_dispatch for message ${msgId}`);
      return new Response('OK', { status: 200 });

    } catch (error) {
      console.error('Error:', error);
      return new Response(JSON.stringify({ error: error.message }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      });
    }
  }
};
