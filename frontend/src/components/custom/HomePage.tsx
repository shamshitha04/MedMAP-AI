"use client";

import { useRef, useEffect, useState } from "react";
import Link from "next/link";
import { motion, useScroll, useTransform } from "framer-motion";
import {
	Pill,
	Shield,
	Zap,
	Database,
	Eye,
	ArrowRight,
	Lock,
	Sparkles,
	Activity,
	Brain,
} from "lucide-react";

/* ══════════════════════════════════════════════════════════════
   ANIMATION VARIANTS
   ══════════════════════════════════════════════════════════════ */

const stagger = {
	hidden: { opacity: 0 },
	show: { opacity: 1, transition: { staggerChildren: 0.12, delayChildren: 0.15 } },
};

const fadeUp = {
	hidden: { opacity: 0, y: 36 },
	show: { opacity: 1, y: 0, transition: { duration: 0.7, ease: [0.22, 0.6, 0.36, 1] } },
};

const fadeIn = {
	hidden: { opacity: 0 },
	show: { opacity: 1, transition: { duration: 0.8 } },
};

const scaleIn = {
	hidden: { opacity: 0, scale: 0.88 },
	show: { opacity: 1, scale: 1, transition: { duration: 0.7, ease: [0.22, 0.6, 0.36, 1] } },
};

/* ══════════════════════════════════════════════════════════════
   FLOATING ORBS (Background decoration)
   ══════════════════════════════════════════════════════════════ */

function FloatingOrbs() {
	return (
		<div className="pointer-events-none fixed inset-0 overflow-hidden">
			<div className="absolute -left-32 top-20 h-[500px] w-[500px] rounded-full bg-brand/[0.04] blur-[120px]" />
			<div className="absolute -right-20 top-[40%] h-[400px] w-[400px] rounded-full bg-safe/[0.03] blur-[100px]" />
			<div className="absolute bottom-20 left-1/3 h-[350px] w-[350px] rounded-full bg-info/[0.03] blur-[100px]" />
		</div>
	);
}

/* ══════════════════════════════════════════════════════════════
   DNA HELIX ANIMATION (Hero visual)
   ══════════════════════════════════════════════════════════════ */

function HelixVisual() {
	const canvasRef = useRef<HTMLCanvasElement>(null);

	useEffect(() => {
		const canvas = canvasRef.current;
		if (!canvas) return;
		const ctx = canvas.getContext("2d");
		if (!ctx) return;

		let animationId: number;
		let time = 0;

		const resize = () => {
			canvas.width = canvas.offsetWidth * 2;
			canvas.height = canvas.offsetHeight * 2;
			ctx.scale(2, 2);
		};
		resize();
		window.addEventListener("resize", resize);

		const draw = () => {
			const w = canvas.offsetWidth;
			const h = canvas.offsetHeight;
			ctx.clearRect(0, 0, w, h);

			const strands = 28;
			const amplitude = w * 0.18;
			const cx = w / 2;

			for (let i = 0; i < strands; i++) {
				const t = i / strands;
				const y = t * h;
				const phase = time + t * Math.PI * 4;

				const x1 = cx + Math.sin(phase) * amplitude;
				const x2 = cx + Math.sin(phase + Math.PI) * amplitude;
				const z1 = Math.cos(phase);
				const z2 = Math.cos(phase + Math.PI);

				// Connecting bar
				ctx.beginPath();
				ctx.moveTo(x1, y);
				ctx.lineTo(x2, y);
				ctx.strokeStyle = `rgba(124, 77, 255, ${0.06 + Math.abs(z1) * 0.06})`;
				ctx.lineWidth = 1;
				ctx.stroke();

				// Nodes
				const r1 = 2.5 + z1 * 1.5;
				const r2 = 2.5 + z2 * 1.5;

				if (z1 > 0) {
					ctx.beginPath();
					ctx.arc(x1, y, Math.max(r1, 1), 0, Math.PI * 2);
					ctx.fillStyle = `rgba(0, 214, 143, ${0.3 + z1 * 0.5})`;
					ctx.fill();
				}
				if (z2 > 0) {
					ctx.beginPath();
					ctx.arc(x2, y, Math.max(r2, 1), 0, Math.PI * 2);
					ctx.fillStyle = `rgba(124, 77, 255, ${0.3 + z2 * 0.5})`;
					ctx.fill();
				}
				if (z1 <= 0) {
					ctx.beginPath();
					ctx.arc(x1, y, Math.max(Math.abs(r1), 1), 0, Math.PI * 2);
					ctx.fillStyle = `rgba(0, 214, 143, ${0.1 + Math.abs(z1) * 0.15})`;
					ctx.fill();
				}
				if (z2 <= 0) {
					ctx.beginPath();
					ctx.arc(x2, y, Math.max(Math.abs(r2), 1), 0, Math.PI * 2);
					ctx.fillStyle = `rgba(124, 77, 255, ${0.1 + Math.abs(z2) * 0.15})`;
					ctx.fill();
				}
			}

			time += 0.008;
			animationId = requestAnimationFrame(draw);
		};

		draw();
		return () => {
			cancelAnimationFrame(animationId);
			window.removeEventListener("resize", resize);
		};
	}, []);

	return <canvas ref={canvasRef} className="h-full w-full" />;
}

/* ══════════════════════════════════════════════════════════════
   FEATURE CARD
   ══════════════════════════════════════════════════════════════ */

function FeatureCard({
	icon: Icon,
	title,
	description,
	accent,
}: {
	icon: typeof Shield;
	title: string;
	description: string;
	accent: string;
}) {
	return (
		<motion.div
			variants={fadeUp}
			whileHover={{ y: -4, transition: { duration: 0.25 } }}
			className="group relative overflow-hidden rounded-2xl border border-white/[0.06] bg-surface/80 p-6 backdrop-blur-sm transition-colors hover:border-white/[0.12]"
		>
			<div
				className="absolute inset-0 opacity-0 transition-opacity duration-500 group-hover:opacity-100"
				style={{
					background: `radial-gradient(300px circle at var(--mouse-x, 50%) var(--mouse-y, 50%), ${accent}06, transparent 60%)`,
				}}
			/>
			<div className="relative z-10">
				<div
					className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl"
					style={{ background: `${accent}15` }}
				>
					<Icon className="h-5 w-5" style={{ color: accent }} />
				</div>
				<h3 className="font-display mb-2 text-[0.95rem] font-bold tracking-tight text-fg">
					{title}
				</h3>
				<p className="text-[0.8rem] leading-relaxed text-fg-dim">{description}</p>
			</div>
		</motion.div>
	);
}

/* ══════════════════════════════════════════════════════════════
   PIPELINE STEP
   ══════════════════════════════════════════════════════════════ */

function PipelineStep({
	step,
	title,
	description,
	accent,
}: {
	step: string;
	title: string;
	description: string;
	accent: string;
}) {
	return (
		<motion.div variants={fadeUp} className="flex gap-5">
			<div className="flex flex-col items-center">
				<div
					className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white"
					style={{ background: accent }}
				>
					{step}
				</div>
				<div className="mt-2 h-full w-px bg-white/[0.06]" />
			</div>
			<div className="pb-10">
				<h4 className="font-display text-sm font-bold tracking-tight text-fg">{title}</h4>
				<p className="mt-1.5 text-[0.8rem] leading-relaxed text-fg-dim">{description}</p>
			</div>
		</motion.div>
	);
}

/* ══════════════════════════════════════════════════════════════
   MAIN HOME PAGE
   ══════════════════════════════════════════════════════════════ */

export default function HomePage() {
	const heroRef = useRef<HTMLDivElement>(null);
	const { scrollYProgress } = useScroll({
		target: heroRef,
		offset: ["start start", "end start"],
	});
	const heroY = useTransform(scrollYProgress, [0, 1], [0, 120]);
	const heroOpacity = useTransform(scrollYProgress, [0, 0.8], [1, 0]);

	return (
		<div className="relative min-h-screen bg-deep text-fg">
			<FloatingOrbs />
			<div className="bg-grid-pattern pointer-events-none fixed inset-0" />

			{/* ═══════════════ NAV ═══════════════ */}
			<motion.nav
				initial={{ opacity: 0, y: -20 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ duration: 0.6 }}
				className="sticky top-0 z-50 border-b border-white/[0.04] bg-deep/60 backdrop-blur-2xl"
			>
				<div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
					<div className="flex items-center gap-3">
						<div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand/15">
							<Pill className="h-[18px] w-[18px] text-brand" />
						</div>
						<span className="font-display text-lg font-extrabold tracking-tight">
							MedMap<span className="text-brand">AI</span>
						</span>
					</div>
					<div className="flex items-center gap-6">
						<a href="#features" className="text-xs font-medium text-fg-dim transition-colors hover:text-fg">
							Features
						</a>
						<Link
							href="/dashboard"
							className="flex items-center gap-2 rounded-lg bg-brand px-4 py-2 text-xs font-bold text-white shadow-[0_2px_16px_rgba(124,77,255,0.25)] transition-all hover:bg-brand/90 hover:shadow-[0_2px_24px_rgba(124,77,255,0.35)]"
						>
							Launch App
							<ArrowRight className="h-3.5 w-3.5" />
						</Link>
					</div>
				</div>
			</motion.nav>

			{/* ═══════════════ HERO ═══════════════ */}
			<section ref={heroRef} className="relative overflow-hidden">
				<motion.div style={{ y: heroY, opacity: heroOpacity }}>
					<div className="mx-auto grid max-w-6xl grid-cols-1 items-center gap-12 px-6 pb-20 pt-24 lg:grid-cols-[1fr_340px] lg:pt-32">
						<motion.div variants={stagger} initial="hidden" animate="show">
							<motion.div variants={fadeIn} className="mb-5">
								<span className="inline-flex items-center gap-2 rounded-full border border-brand/20 bg-brand/[0.06] px-3.5 py-1.5 text-[10px] font-bold uppercase tracking-[0.16em] text-brand">
									<Sparkles className="h-3 w-3" />
									Explainable AI · Clinical Safety
								</span>
							</motion.div>

							<motion.h1
								variants={fadeUp}
								className="font-display text-[2.75rem] font-extrabold leading-[1.08] tracking-tight text-fg md:text-[3.5rem] lg:text-[4rem]"
							>
								MedMap-<span className="bg-gradient-to-r from-brand via-info to-safe bg-clip-text text-transparent">AI</span>
							</motion.h1>

							<motion.p
								variants={fadeUp}
								className="mt-4 font-display text-lg font-semibold tracking-tight text-fg-dim md:text-xl lg:text-2xl"
							>
								Eliminate Dispensing Errors
								<br />
								with Deterministic AI
							</motion.p>

							<motion.p
								variants={fadeUp}
								className="mt-6 max-w-lg text-[0.95rem] leading-relaxed text-fg-dim"
							>
								MedMap AI wraps LLM extractions in strict, object-oriented clinical
								guardrails — cross-referencing every result against a local pharmaceutical
								ground truth before it reaches a patient.
							</motion.p>

							<motion.div variants={fadeUp} className="mt-8 flex items-center gap-4">
								<Link
									href="/dashboard"
									className="group flex items-center gap-2.5 rounded-xl bg-brand px-7 py-3.5 text-sm font-bold text-white shadow-[0_4px_24px_rgba(124,77,255,0.3)] transition-all hover:bg-brand/90 hover:shadow-[0_4px_32px_rgba(124,77,255,0.4)] active:scale-[0.98]"
								>
									<Zap className="h-4 w-4 transition-transform group-hover:scale-110" />
									Open Dashboard
								</Link>
							</motion.div>
						</motion.div>

						{/* Helix Visual */}
						<motion.div
							variants={scaleIn}
							initial="hidden"
							animate="show"
							className="hidden h-[420px] lg:block"
						>
							<HelixVisual />
						</motion.div>
					</div>
				</motion.div>
			</section>

			{/* ═══════════════ FEATURES ═══════════════ */}
			<section id="features" className="relative py-24">
				<div className="mx-auto max-w-6xl px-6">
					<motion.div
						variants={stagger}
						initial="hidden"
						whileInView="show"
						viewport={{ once: true, margin: "-80px" }}
						className="text-center"
					>
						<motion.span
							variants={fadeIn}
							className="text-[10px] font-bold uppercase tracking-[0.2em] text-brand"
						>
							Architectural Pillars
						</motion.span>
						<motion.h2
							variants={fadeUp}
							className="font-display mx-auto mt-4 max-w-xl text-2xl font-extrabold tracking-tight md:text-3xl"
						>
							Safety by Design,{" "}
							<span className="text-brand">Not by Chance</span>
						</motion.h2>
						<motion.p variants={fadeUp} className="mx-auto mt-4 max-w-md text-sm text-fg-dim">
							Every component of MedMap AI is engineered to prevent pharmaceutical errors
							through deterministic, explainable logic.
						</motion.p>
					</motion.div>

					<motion.div
						variants={stagger}
						initial="hidden"
						whileInView="show"
						viewport={{ once: true, margin: "-80px" }}
						className="mt-14 grid gap-5 md:grid-cols-2 lg:grid-cols-3"
					>
						<FeatureCard
							icon={Eye}
							title="Vision Extraction"
							accent="#42a5f5"
							description="OpenAI gpt-4o-mini processes prescription images with structured outputs — strict Pydantic schemas enforce data integrity at extraction time."
						/>
						<FeatureCard
							icon={Brain}
							title="Hybrid Vector Search"
							accent="#7c4dff"
							description="Pinecone Serverless combines dense (MiniLM-L6-v2) and sparse (BM25) vectors for precision medicine matching with variant-aware penalties."
						/>
						<FeatureCard
							icon={Database}
							title="SQLite Ground Truth"
							accent="#00d68f"
							description="Every matched result is cross-referenced against a local relational database. Strength, form, and combination flags are overridden from verified records."
						/>
						<FeatureCard
							icon={Shield}
							title="Pre-Match Guardrails"
							accent="#ffa726"
							description="Variant numbers are stripped from brand names. Text is normalized. Hallucinated dosage assumptions are blocked before embeddings are generated."
						/>
						<FeatureCard
							icon={Lock}
							title="Post-Match Locking"
							accent="#ff4757"
							description="Combination products are locked as single entities. Strength is always injected from the database, permanently overriding LLM extractions."
						/>
						<FeatureCard
							icon={Activity}
							title="Audit Trail"
							accent="#00d68f"
							description="Every guardrail trigger is logged in a transparent array. Each decision is traceable, deterministic, and fully explainable to clinical staff."
						/>
					</motion.div>
				</div>
			</section>
		</div>
	);
}
