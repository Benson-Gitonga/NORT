// app/layout.js or app/layout.tsx

export const metadata = {
  title: 'Nort App',
  other: {
    'base:app_id': '69ef725c7e92b7a4af93efb6',
  },
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}