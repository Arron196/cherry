# Frontend Module (Next.js)

> Language / 语言:
> - English: [`README.en.md`](README.en.md)
> - 中文: [`README.zh-CN.md`](README.zh-CN.md)

This file is the bilingual entry for frontend documentation.

This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

`npm run dev` 使用自定义脚本自动选择可用端口，请以终端实际输出地址为准。

若通过项目根目录 `docker compose` 启动前端，对外访问端口默认为 [http://localhost:18940](http://localhost:18940)（容器内仍为 `3000`）。

## Anchoring / 区块链接口说明

- 当前环境默认是 **mock 锚定**（后端 `ANCHOR_ADAPTER=active_mock`），用于联调与验收，不要求真实链节点。
- 前端可正常使用并依赖以下正式接口：
  - `GET /admin/anchoring/tasks`
  - `POST /admin/anchoring/tasks/{ingest_request_id}/requeue`
  - `POST /admin/anchoring/run-once`
  - `GET /v1/trace/{batch_id}`（包含 `anchor.transaction_hash`）
- 后续如接入真实链，目标是通过后端适配器切换实现，不破坏现有前端契约。

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
