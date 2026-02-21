import "./globals.css";

import type { ReactNode } from "react";
import type { Metadata } from "next";
import { Syne, DM_Sans, JetBrains_Mono } from "next/font/google";

const syne = Syne({
	subsets: ["latin"],
	variable: "--font-syne",
	display: "swap",
	weight: ["400", "500", "600", "700", "800"],
});

const dmSans = DM_Sans({
	subsets: ["latin"],
	variable: "--font-dm-sans",
	display: "swap",
	weight: ["400", "500", "600", "700"],
});

const jetbrainsMono = JetBrains_Mono({
	subsets: ["latin"],
	variable: "--font-jetbrains",
	display: "swap",
	weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
	title: "MedMap AI · Clinical Decision Support",
	description:
		"Deterministic, Explainable AI prescription analysis with clinical guardrails.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
	return (
		<html
			lang="en"
			className={`${syne.variable} ${dmSans.variable} ${jetbrainsMono.variable}`}
		>
			<body>{children}</body>
		</html>
	);
}

