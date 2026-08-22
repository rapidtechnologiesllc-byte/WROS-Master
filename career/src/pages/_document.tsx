import { Html, Head, Main, NextScript } from 'next/document'

export default function Document() {
  return (
    <Html lang="en" suppressHydrationWarning>
      <Head />
      <body>
        <style>{`
          /* BlitzenX Brand Kit v3.0 - Career Site */
          :root {
            /* Brand Colors */
            --bx-orange: #F58220;
            --bx-orange-hover: #D96E14;
            --bx-navy: #0B1F3A;
            --bx-slate: #2E3A4D;
            --bx-white: #FFFFFF;
            --bx-light: #F4F6F8;
            --bx-border: #D9E2EC;

            /* Semantic Colors */
            --surface-0: #F4F6F8;
            --surface-1: #FFFFFF;
            --surface-2: #F9FAFB;
            --text-primary: #0B1F3A;
            --text-secondary: #2E3A4D;
            --text-muted: #6B7280;
            --border: #D9E2EC;
            --radius: 12px;

            /* Status Colors */
            --success: #10B981;
            --warning: #F59E0B;
            --error: #EF4444;
            --info: #3B82F6;
          }

          * { margin: 0; padding: 0; box-sizing: border-box; }

          body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--surface-0);
            color: var(--text-primary);
            line-height: 1.6;
          }

          a { color: inherit; text-decoration: none; }

          /* Smooth transitions */
          * {
            transition: background-color 0.2s, border-color 0.2s, color 0.2s;
          }
        `}</style>
        <Main />
        <NextScript />
      </body>
    </Html>
  )
}
