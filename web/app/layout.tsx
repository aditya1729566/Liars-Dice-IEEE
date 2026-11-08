import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = { title: 'BLUFF.EXE — Call the bluff', description: 'A five-dice game against AI with a post-match decision journal.' };
export default function RootLayout({ children }: Readonly<{children: React.ReactNode}>) { return <html lang="en"><body>{children}</body></html>; }
