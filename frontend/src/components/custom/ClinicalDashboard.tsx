"use client";

import {
	type DragEvent,
	type FormEvent,
	type KeyboardEvent,
	type ReactNode,
	useEffect,
	useMemo,
	useRef,
	useState,
} from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
	Shield,
	Upload,
	AlertTriangle,
	CheckCircle2,
	FileText,
	Pill,
	X,
	Loader2,
	Sparkles,
	Lock,
	Zap,
} from "lucide-react";
import type {
	ExtractionResponse,
	MatchedMedicine,
	ProcessedMedicine,
} from "../../types/api";

/* ══════════════════════════════════════════════════════════════════════
   ANIMATION VARIANTS
   ══════════════════════════════════════════════════════════════════════ */

const stagger = {
	hidden: { opacity: 0 },
	show: {
		opacity: 1,
		transition: { staggerChildren: 0.12, delayChildren: 0.08 },
	},
};

const fadeUp = {
	hidden: { opacity: 0, y: 24 },
	show: {
		opacity: 1,
		y: 0,
		transition: { duration: 0.5, ease: [0.25, 0.4, 0.25, 1] },
	},
};

/* ══════════════════════════════════════════════════════════════════════
   COLOUR HELPERS
   ══════════════════════════════════════════════════════════════════════ */

function riskBadgeCls(level: string): string {
	if (level === "High") return "border-safe/30 bg-safe/10 text-safe";
	if (level === "Medium") return "border-caution/30 bg-caution/10 text-caution";
	return "border-danger/30 bg-danger/10 text-danger";
}

function tierBadgeCls(level: string): string {
	if (level === "High") return "border-danger/30 bg-danger/10 text-danger";
	if (level === "Medium") return "border-caution/30 bg-caution/10 text-caution";
	return "border-safe/30 bg-safe/10 text-safe";
}

function scoreHex(pct: number): string {
	if (pct >= 85) return "#00d68f";
	if (pct >= 60) return "#ffa726";
	return "#ff4757";
}

function scoreBadgeCls(pct: number): string {
	if (pct >= 85) return "border-safe/30 bg-safe/10 text-safe";
	if (pct >= 60) return "border-caution/30 bg-caution/10 text-caution";
	return "border-danger/30 bg-danger/10 text-danger";
}

/* ══════════════════════════════════════════════════════════════════════
   SUB-COMPONENTS
   ══════════════════════════════════════════════════════════════════════ */

function ConfidenceRing({ score }: { score: number }) {
	const pct = Math.round(score * 100);
	const r = 52;
	const circ = 2 * Math.PI * r;
	const offset = circ * (1 - score);
	const hex = scoreHex(pct);

	return (
		<div className="relative flex shrink-0 items-center justify-center">
			<svg viewBox="0 0 120 120" className="h-32 w-32">
				<defs>
					<filter id="ring-glow">
						<feGaussianBlur stdDeviation="2.5" result="blur" />
						<feMerge>
							<feMergeNode in="blur" />
							<feMergeNode in="SourceGraphic" />
						</feMerge>
					</filter>
				</defs>
				<circle
					cx="60"
					cy="60"
					r={r}
					fill="none"
					stroke="rgba(255,255,255,0.04)"
					strokeWidth="7"
				/>
				<motion.circle
					cx="60"
					cy="60"
					r={r}
					fill="none"
					stroke={hex}
					strokeWidth="7"
					strokeLinecap="round"
					strokeDasharray={circ}
					initial={{ strokeDashoffset: circ }}
					animate={{ strokeDashoffset: offset }}
					transition={{ duration: 1.3, ease: "easeOut", delay: 0.25 }}
					transform="rotate(-90 60 60)"
					filter="url(#ring-glow)"
				/>
			</svg>
			<div className="absolute flex flex-col items-center">
				<span
					className="font-display text-3xl font-extrabold leading-none"
					style={{ color: hex }}
				>
					{pct}
					<span className="text-lg font-bold">%</span>
				</span>
				<span className="mt-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-fg-faint">
					confidence
				</span>
			</div>
		</div>
	);
}

function StatusOrb({ active }: { active: boolean }) {
	return (
		<div className="flex items-center gap-2.5">
			<span className="relative flex h-2.5 w-2.5">
				{active && (
					<span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-info opacity-75" />
				)}
				<span
					className={`relative inline-flex h-2.5 w-2.5 rounded-full ${active ? "bg-info" : "bg-safe"}`}
				/>
			</span>
			<span className="text-xs font-medium tracking-wide text-fg-dim">
				{active ? "Analyzing…" : "System Ready"}
			</span>
		</div>
	);
}

function Tag({
	children,
	className = "",
}: {
	children: ReactNode;
	className?: string;
}) {
	return (
		<span
			className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-bold tracking-wide ${className}`}
		>
			{children}
		</span>
	);
}

function DataCell({
	label,
	value,
	accent,
}: {
	label: string;
	value: string;
	accent?: "safe" | "danger" | "caution" | "info";
}) {
	const map: Record<string, string> = {
		safe: "border-safe/15 bg-safe/[0.04]",
		danger: "border-danger/15 bg-danger/[0.04]",
		caution: "border-caution/15 bg-caution/[0.04]",
		info: "border-info/15 bg-info/[0.04]",
	};
	const cls = accent ? map[accent] : "border-white/[0.06] bg-white/[0.02]";

	return (
		<div className={`rounded-xl border p-4 ${cls}`}>
			<p className="text-[10px] font-bold uppercase tracking-[0.12em] text-fg-faint">
				{label}
			</p>
			<p className="mt-1.5 text-sm font-semibold text-fg">{value}</p>
		</div>
	);
}

function MatchBadges({ med }: { med: MatchedMedicine }) {
	const pct = med.final_similarity_score * 100;
	return (
		<div className="flex flex-wrap items-center gap-2">
			<Tag className={riskBadgeCls(med.risk_classification)}>
				Confidence: {med.risk_classification}
			</Tag>
			<Tag className={tierBadgeCls(med.clinical_risk_tier)}>
				Risk Tier: {med.clinical_risk_tier}
			</Tag>
			<Tag className={scoreBadgeCls(pct)}>
				Score: {pct.toFixed(1)}%
			</Tag>
			<Tag
				className={
					med.manual_review_required
						? "border-danger/30 bg-danger/10 text-danger"
						: "border-safe/30 bg-safe/10 text-safe"
				}
			>
				{med.manual_review_required ? "⚠ Review Required" : "✓ Verified"}
			</Tag>
		</div>
	);
}

function GlassPanel({
	children,
	className = "",
}: {
	children: ReactNode;
	className?: string;
}) {
	return (
		<div
			className={`rounded-2xl border border-white/[0.06] bg-surface ${className}`}
		>
			{children}
		</div>
	);
}

/* ══════════════════════════════════════════════════════════════════════
   MAIN COMPONENT
   ══════════════════════════════════════════════════════════════════════ */

type Props = { apiUrl: string };

export default function ClinicalDashboard({ apiUrl }: Props) {
	const [mounted, setMounted] = useState(false);
	const [rawText, setRawText] = useState("Augmentin 625 Tab BD");
	const [prescriberId, setPrescriberId] = useState("dr-1");
	const [file, setFile] = useState<File | null>(null);
	const [dragActive, setDragActive] = useState(false);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [data, setData] = useState<ExtractionResponse | null>(null);
	const fileInputRef = useRef<HTMLInputElement | null>(null);

	// Hydration guard: prevent framer-motion from baking opacity:0 into SSR HTML
	useEffect(() => { setMounted(true); }, []);

	const item: ProcessedMedicine | undefined = data?.medicines?.[0];
	const variantToken = item?.extracted?.variant || null;

	const allLogs: string[] = useMemo(() => {
		const merged = [
			...(item?.guardrail_logs ?? []),
			...(data?.guardrail_logs ?? []),
		];
		return [...new Set(merged)];
	}, [item, data]);

	const flowAWarning = useMemo(() => {
		if (!item) return null;
		if (!item.extracted.variant)
			return "No risky numeric assumption detected in the raw extraction.";
		return `Potentially unsafe: "${item.extracted.variant}" interpreted as dosage strength without deterministic grounding.`;
	}, [item]);

	const selectedFileLabel = useMemo(() => {
		if (!file) return null;
		return `${file.name} · ${Math.max(1, Math.round(file.size / 1024))} KB`;
	}, [file]);

	const toBase64Payload = (f: File): Promise<string> =>
		new Promise((resolve, reject) => {
			const reader = new FileReader();
			reader.onload = () => {
				const result = reader.result;
				if (typeof result !== "string")
					return reject(new Error("Read failed"));
				const b64 = result.includes(",") ? result.split(",")[1] : result;
				if (!b64) return reject(new Error("Empty base64 payload"));
				resolve(b64);
			};
			reader.onerror = () => reject(new Error("File conversion failed"));
			reader.readAsDataURL(f);
		});

	const handleDrop = (e: DragEvent<HTMLDivElement>) => {
		e.preventDefault();
		setDragActive(false);
		const dropped = e.dataTransfer.files?.[0];
		if (dropped) setFile(dropped);
	};

	const clearFile = () => {
		setFile(null);
		if (fileInputRef.current) fileInputRef.current.value = "";
	};

	const openFilePicker = () => {
		fileInputRef.current?.click();
	};

	const handleDropzoneKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
		if (e.key === "Enter" || e.key === " ") {
			e.preventDefault();
			openFilePicker();
		}
	};

	const runAnalysis = async (e: FormEvent<HTMLFormElement>) => {
		e.preventDefault();
		setLoading(true);
		setError(null);

		try {
			const trimmedText = rawText.trim();
			const trimmedPrescriber = prescriberId.trim() || null;

			let body: {
				image_base64: string | null;
				raw_text: string | null;
				prescriber_id: string | null;
			};

			if (file) {
				body = {
					image_base64: await toBase64Payload(file),
					raw_text: null,
					prescriber_id: trimmedPrescriber,
				};
			} else {
				if (!trimmedText)
					throw new Error(
						"Enter prescription text or upload an image before analyzing.",
					);
				body = {
					raw_text: trimmedText,
					image_base64: null,
					prescriber_id: trimmedPrescriber,
				};
			}

			const res = await fetch(apiUrl, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify(body),
			});

			if (!res.ok) {
				const text = await res.text();
				throw new Error(text || `Request failed: ${res.status}`);
			}

			setData((await res.json()) as ExtractionResponse);
		} catch (err) {
			setError(err instanceof Error ? err.message : "Unknown error");
			setData(null);
		} finally {
			setLoading(false);
		}
	};

	/* ═════════════════════════════════════════════════════════════════
	   RENDER
	   ═════════════════════════════════════════════════════════════════ */

	return (
		<div className="relative min-h-screen bg-deep text-fg">
			{/* Background effects */}
			<div className="bg-grid-pattern pointer-events-none fixed inset-0" />
			<div className="pointer-events-none fixed left-1/2 top-0 h-[700px] w-[1100px] -translate-x-1/2 rounded-full bg-brand/[0.035] blur-[140px]" />

			{/* Content */}
			<div className="relative z-10">
				{/* ═══════════════ HEADER ═══════════════ */}
				<motion.header
					initial={mounted ? { opacity: 0, y: -14 } : false}
					animate={{ opacity: 1, y: 0 }}
					transition={{ duration: 0.5 }}
					className="sticky top-0 z-30 border-b border-white/[0.04] bg-deep/80 backdrop-blur-2xl"
				>
					<div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
						<div className="flex items-center gap-3">
							<div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand/15">
								<Pill className="h-5 w-5 text-brand" />
							</div>
							<div>
								<h1 className="font-display text-lg font-extrabold tracking-tight text-fg">
									MedMap
									<span className="ml-1.5 text-brand">AI</span>
								</h1>
								<p className="text-[11px] font-medium tracking-[0.08em] text-fg-faint">
									CLINICAL DECISION SUPPORT
								</p>
							</div>
						</div>
						<StatusOrb active={loading} />
					</div>
				</motion.header>

				{/* ═══════════════ PAGE CONTENT ═══════════════ */}
				<motion.div
					variants={stagger}
					initial={mounted ? "hidden" : false}
					animate="show"
					className="mx-auto max-w-7xl space-y-6 px-6 py-8"
				>
					{/* ──────────────────────────────────────
					    INPUT SECTION (full width, horizontal)
					    ────────────────────────────────────── */}
					<motion.section variants={fadeUp}>
						<GlassPanel className="p-6">
							<form onSubmit={runAnalysis}>
								<div className="grid grid-cols-1 items-stretch gap-6 lg:grid-cols-2">
									{/* Text input */}
									<div className="flex flex-col">
										<label htmlFor="prescription-text" className="mb-2 flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-fg-dim">
											<FileText className="h-4 w-4 text-brand" />
											Prescription Text
										</label>
										<textarea
											id="prescription-text"
											className="min-h-[184px] flex-1 w-full resize-none rounded-xl border border-white/[0.06] bg-elevated px-4 py-3 text-sm leading-relaxed text-fg placeholder:text-fg-faint transition-all focus:border-brand/40 focus:outline-none focus:ring-2 focus:ring-brand/20"
											value={rawText}
											onChange={(e) => setRawText(e.target.value)}
											placeholder="e.g. Augmentin 625 Tab BD"
										/>
									</div>

									{/* Upload zone */}
									<div className="flex flex-col">
										<label htmlFor="prescription-file" className="mb-2 flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-fg-dim">
											<Upload className="h-4 w-4 text-brand" />
											Visual Scan / PDF
										</label>
										<div
											onDragEnter={(e) => {
												e.preventDefault();
												setDragActive(true);
											}}
											onDragOver={(e) => {
												e.preventDefault();
												setDragActive(true);
											}}
											onDragLeave={(e) => {
												e.preventDefault();
												setDragActive(false);
											}}
											onDrop={handleDrop}
											onClick={openFilePicker}
											onKeyDown={handleDropzoneKeyDown}
											role="button"
											tabIndex={0}
											aria-label="Upload prescription file"
											className={`flex min-h-[184px] flex-1 cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed transition-all ${
												dragActive
													? "border-brand/50 bg-brand/[0.06]"
													: "border-white/[0.08] bg-elevated/30 hover:border-white/[0.16] hover:bg-elevated/50"
											}`}
										>
											<Upload className="mb-3 h-8 w-8 text-fg-faint" />
											<p className="text-sm font-medium text-fg-dim">
												Drop file here or click to browse
											</p>
											<p className="mt-1 text-xs text-fg-faint">
												PNG · JPG · PDF
											</p>
											<input
												id="prescription-file"
												ref={fileInputRef}
												type="file"
												className="hidden"
												accept=".png,.jpg,.jpeg,.pdf"
												onChange={(e) =>
													setFile(e.target.files?.[0] ?? null)
												}
											/>
											<AnimatePresence>
												{file && (
													<motion.div
														initial={{ opacity: 0, height: 0 }}
														animate={{ opacity: 1, height: "auto" }}
														exit={{ opacity: 0, height: 0 }}
															onClick={(e) => e.stopPropagation()}
															className="mt-3 flex items-center justify-between overflow-hidden rounded-lg border border-brand/20 bg-brand/[0.06] px-4 py-2.5"
														>
															<span className="truncate text-xs font-medium text-brand">
																{selectedFileLabel}
															</span>
															<button
																type="button"
																onClick={(e) => { e.stopPropagation(); clearFile(); }}
															className="ml-3 text-fg-faint transition-colors hover:text-danger"
														>
															<X className="h-4 w-4" />
														</button>
													</motion.div>
												)}
											</AnimatePresence>
										</div>
									</div>
								</div>

								{/* Prescriber ID + Submit Button */}
								<div className="mt-6 grid grid-cols-1 items-end gap-4 sm:grid-cols-[minmax(0,1fr)_auto]">
									<div className="min-w-0">
										<label htmlFor="prescriber-id" className="mb-2 flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-fg-dim">
											Prescriber ID{" "}
											<span className="text-fg-faint">(optional)</span>
										</label>
										<input
											id="prescriber-id"
											className="w-full rounded-xl border border-white/[0.06] bg-elevated px-4 py-3 text-sm text-fg placeholder:text-fg-faint transition-all focus:border-brand/40 focus:outline-none focus:ring-2 focus:ring-brand/20"
											value={prescriberId}
											onChange={(e) =>
												setPrescriberId(e.target.value)
											}
											placeholder="e.g. DR-001"
										/>
									</div>
									<button
										type="submit"
										disabled={loading}
										className="group flex w-full shrink-0 items-center justify-center gap-2.5 rounded-xl border border-transparent bg-brand px-10 py-3 text-sm font-bold text-white shadow-[0_4px_24px_rgba(124,77,255,0.25)] transition-all hover:bg-brand/90 hover:shadow-[0_4px_32px_rgba(124,77,255,0.35)] active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
									>
										{loading ? (
											<>
												<Loader2 className="h-4 w-4 animate-spin" />
												Analyzing…
											</>
										) : (
											<>
												<Zap className="h-4 w-4 transition-transform group-hover:scale-110" />
												Analyze Prescription
											</>
										)}
									</button>
								</div>
							</form>
						</GlassPanel>
					</motion.section>

					{/* Error */}
					<AnimatePresence>
						{error && (
							<motion.div
								initial={{ opacity: 0, y: -10 }}
								animate={{ opacity: 1, y: 0 }}
								exit={{ opacity: 0, y: -10 }}
								className="rounded-xl border border-danger/20 bg-danger/[0.06] px-6 py-4 text-sm text-danger"
							>
								<strong className="font-bold">Error:&nbsp;</strong>
								{error}
							</motion.div>
						)}
					</AnimatePresence>

					{/* ──────────────────────────────────────
					    FLOW A + FLOW B (side by side)
					    ────────────────────────────────────── */}
					<motion.section
						variants={fadeUp}
						className="grid grid-cols-1 items-stretch gap-6 md:grid-cols-2"
					>
						{/* ───── FLOW A : Raw Extraction ───── */}
						<GlassPanel className="flex h-full flex-col overflow-hidden border-danger/10">
							<div className="border-b border-danger/[0.08] bg-danger/[0.03] px-6 py-5">
								<div className="flex items-center gap-2.5">
									<span className="block h-2.5 w-2.5 shrink-0 rounded-full bg-danger shadow-[0_0_8px_rgba(255,71,87,0.6)]" />
									<h2 className="font-display text-base font-bold tracking-tight">
										Flow A — Raw Extraction
									</h2>
								</div>
								<p className="mt-1.5 text-xs text-fg-faint">
									Unpenalized LLM output — may contain hallucinated
									assumptions
								</p>
							</div>

							<div className="flex flex-1 flex-col gap-5 p-6">
								{/* warning */}
								<div className="flex items-start gap-3 rounded-xl border border-danger/15 bg-danger/[0.04] px-4 py-3.5">
									<AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-danger/80" />
									<p className="text-xs leading-relaxed text-danger/70">
										{flowAWarning ??
											"Run analysis to inspect raw extraction assumptions."}
									</p>
								</div>

								{/* variant token */}
								<div className="flex items-center gap-2.5 text-xs text-fg-dim">
									<span>Hallucination risk token:</span>
									<Tag className="border-danger/30 bg-danger/10 text-danger">
										{variantToken ?? "—"}
									</Tag>
								</div>

								{/* raw JSON */}
								<pre className="font-code min-h-0 flex-1 overflow-auto rounded-xl border border-white/[0.04] bg-deep p-5 text-xs leading-relaxed text-fg-dim">
									{item
										? JSON.stringify(item.extracted, null, 2)
										: "// No extraction data yet."}
								</pre>
							</div>
						</GlassPanel>

						{/* ───── FLOW B : Grounded Match ───── */}
						<GlassPanel className="flex h-full flex-col overflow-hidden border-safe/10">
							<div className="border-b border-safe/[0.08] bg-safe/[0.03] px-6 py-5">
								<div className="flex items-center gap-2.5">
									<span className="block h-2.5 w-2.5 shrink-0 rounded-full bg-safe shadow-[0_0_8px_rgba(0,214,143,0.6)]" />
									<h2 className="font-display text-base font-bold tracking-tight">
										Flow B — Grounded Match
									</h2>
								</div>
								<p className="mt-1.5 text-xs text-fg-faint">
									Deterministically verified against local formulary
								</p>
							</div>

							<div className="flex flex-1 flex-col gap-5 p-6">
								{!item ? (
									<div className="flex flex-1 flex-col items-center justify-center text-fg-faint">
										<CheckCircle2 className="mb-4 h-12 w-12 opacity-15" />
										<p className="text-sm">
											Run analysis to view grounded output.
										</p>
									</div>
								) : (
									<AnimatePresence mode="wait">
										<motion.div
											key="results"
											initial={{ opacity: 0, scale: 0.97 }}
											animate={{ opacity: 1, scale: 1 }}
											transition={{
												duration: 0.4,
												ease: "easeOut",
											}}
											className="space-y-5"
										>
											{/* confidence ring + badges */}
											<div className="flex items-start gap-6">
												<ConfidenceRing
													score={
														item.matched_medicine
															.final_similarity_score
													}
												/>
												<div className="flex-1 pt-4">
													<MatchBadges
														med={item.matched_medicine}
													/>
												</div>
											</div>

											{/* data grid */}
											<div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
												<DataCell
													label="Brand Name"
													value={
														item.matched_medicine.brand_name
													}
												/>
												<DataCell
													label="Variant (Extracted)"
													value={
														item.extracted.variant || "—"
													}
												/>
												<DataCell
													label="Generic Backbone"
													value={
														item.matched_medicine
															.generic_name
													}
												/>
												<DataCell
													label="Physical Form"
													value={
														item.matched_medicine.form
													}
												/>

												<div className="sm:col-span-2">
													<DataCell
														label="Official Strength (SQLite Ground Truth)"
														value={
															item.matched_medicine
																.official_strength
														}
														accent="safe"
													/>
												</div>

												<div className="flex items-center gap-3 rounded-xl border border-white/[0.06] bg-white/[0.02] p-4 sm:col-span-2">
													<Lock className="h-4 w-4 shrink-0 text-fg-faint" />
													<span className="text-[10px] font-bold uppercase tracking-[0.12em] text-fg-faint">
														Combination Product
													</span>
													<Tag
														className={
															item.matched_medicine
																.combination_flag
																? "border-info/30 bg-info/10 text-info"
																: "border-white/10 bg-white/[0.03] text-fg-dim"
														}
													>
														{item.matched_medicine
															.combination_flag
															? "Locked as single product"
															: "No"}
													</Tag>
												</div>
											</div>
										</motion.div>
									</AnimatePresence>
								)}
							</div>
						</GlassPanel>
					</motion.section>

					{/* ──────────────────────────────────────
					    GUARDRAIL AUDIT TRAIL
					    ────────────────────────────────────── */}
					<motion.section variants={fadeUp}>
						<GlassPanel className="overflow-hidden border-caution/10">
							<div className="border-b border-caution/[0.08] bg-caution/[0.03] px-6 py-5">
								<div className="flex items-center gap-3">
									<Shield className="h-5 w-5 text-caution" />
									<h2 className="font-display text-base font-bold tracking-tight">
										Guardrail Audit Trail
									</h2>
									<Tag className="border-caution/30 bg-caution/10 text-caution">
										{allLogs.length} entries
									</Tag>
								</div>
								<p className="mt-1.5 text-xs text-fg-faint">
									Every deterministic guardrail rule that fired during
									this extraction is listed below for full clinical
									transparency.
								</p>
							</div>

							<div className="p-6">
								{allLogs.length === 0 ? (
									<div className="flex flex-col items-center py-12 text-fg-faint">
										<Sparkles className="mb-4 h-10 w-10 opacity-15" />
										<p className="text-sm">
											No guardrail events recorded. Run an analysis
											to populate the audit trail.
										</p>
									</div>
								) : (
									<ol className="space-y-2.5">
										{allLogs.map((log, i) => (
											<motion.li
												key={`${log.slice(0, 20)}-${i}`}
												initial={{ opacity: 0, x: -16 }}
												animate={{ opacity: 1, x: 0 }}
												transition={{
													delay: i * 0.04,
													duration: 0.35,
													ease: "easeOut",
												}}
												className="flex items-start gap-4 rounded-xl border border-white/[0.04] bg-elevated/40 px-5 py-4"
											>
												<span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-caution/15 text-[11px] font-extrabold text-caution">
													{i + 1}
												</span>
												<span className="text-sm leading-relaxed text-fg-dim">
													{log}
												</span>
											</motion.li>
										))}
									</ol>
								)}
							</div>
						</GlassPanel>
					</motion.section>
				</motion.div>
			</div>
		</div>
	);
}
