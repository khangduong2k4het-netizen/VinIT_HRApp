import type { Metadata } from 'next';
import './globals.css';
import ThemeRegistry from '@/components/layout/ThemeRegistry';
import AppLayout from '@/components/layout/AppLayout';
import { I18nProvider } from '@/i18n/I18nProvider';
import { AppRouterCacheProvider } from '@mui/material-nextjs/v15-appRouter';

export const metadata: Metadata = {
  title: 'VinUni HRA — CV Screening Workspace',
  description: 'HR Resource Workspace for VinUniversity HR',
  icons: {
    icon: '/vinuni-logo.png',
    shortcut: '/vinuni-logo.png',
    apple: '/vinuni-logo.png',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        {/* eslint-disable-next-line @next/next/no-page-custom-font */}
        <link
          href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:ital,wght@0,400;0,500;0,600;0,700;1,400&family=JetBrains+Mono:wght@500;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body suppressHydrationWarning={true}>
        <AppRouterCacheProvider>
          <I18nProvider>
            <ThemeRegistry>
              <AppLayout>{children}</AppLayout>
            </ThemeRegistry>
          </I18nProvider>
        </AppRouterCacheProvider>
      </body>
    </html>
  );
}
