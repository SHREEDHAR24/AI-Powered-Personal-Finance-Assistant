import type { Metadata } from "next";
import { DM_Sans } from "next/font/google";
import "./globals.css";

const dm = DM_Sans({
  variable: "--font-dm",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "FinMate",
  description: "Personal finance, calculated from your own transactions.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `try{if(localStorage.getItem("theme")==="dark")document.documentElement.classList.add("dark")}catch(e){}`,
          }}
        />
      </head>
      <body className={`${dm.variable} antialiased`}>{children}</body>
    </html>
  );
}
