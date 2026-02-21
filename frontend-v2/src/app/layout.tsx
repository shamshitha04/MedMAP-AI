import "./globals.css";

import type { ReactNode } from "react";
import type { Metadata } from "next";
import { Fraunces, Figtree, Fira_Code } from "next/font/google";

const fraunces = Fraunces({
	subsets: ["latin"],
	variable: "--font-fraunces",
	display: "swap",
	weight: ["400", "500", "600", "700", "800", "900"],
});

const figtree = Figtree({
	subsets: ["latin"],
	variable: "--font-figtree",
	display: "swap",
	weight: ["400", "500", "600", "700", "800"],
});

const firaCode = Fira_Code({
	subsets: ["latin"],
	variable: "--font-fira-code",
	display: "swap",
	weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
	title: "MedMap AI · Pharmaceutical Ledger",
	description:
		"Deterministic, Explainable AI prescription analysis with clinical guardrails — Apothecary Edition.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
	return (
		<html
			lang="en"
			className={`${fraunces.variable} ${figtree.variable} ${firaCode.variable}`}
		>
			<body className="grain-overlay">{children}</body>
		</html>
	);
}
