import "./globals.css";
import "./theme.css";
import { THEME_BOOTSTRAP } from "@/lib/theme";
export const metadata = { title: "视觉文档检索与证据定位系统" };
export default function RootLayout({ children }: Readonly<{children: React.ReactNode}>) {
  return <html lang="zh-CN" data-theme="dark" suppressHydrationWarning><head><script dangerouslySetInnerHTML={{ __html: THEME_BOOTSTRAP }}/></head><body>{children}</body></html>;
}
