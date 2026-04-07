import type { Metadata } from "next";
import QueryProvider from "@/components/providers/query-provider";
import "@/app/globals.css";

export const metadata: Metadata = {
  title: "Cherry Trace | 樱桃供应链溯源平台",
  description: "面向高价值供应链的可视化溯源与质量监管控制台。",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body className="font-sans antialiased">
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-slate-900 focus:px-4 focus:py-2 focus:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
        >
          跳到主内容
        </a>
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
