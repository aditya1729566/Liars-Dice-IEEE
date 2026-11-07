import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = { title: 'BLUFF.EXE — The AI knows the odds', description: 'A live battle of bids, dice, and nerve.' };
export default function RootLayout({ children }: Readonly<{children: React.ReactNode}>) { return <html lang="en"><body>{children}</body></html>; }
