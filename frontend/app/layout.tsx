import "./globals.css";
export const metadata = { title: "视觉文档检索与证据定位系统" };
export default function RootLayout({ children }: Readonly<{children: React.ReactNode}>) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}
