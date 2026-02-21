"use client";

import { useState, useRef, useCallback, type DragEvent, type ChangeEvent } from "react";
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
  Feather,
  Lock,
  FlaskConical,
} from "lucide-react";

import type { ExtractionResponse, ProcessedMedicine } from "../types/api";

/* ─── animation variants ─── */
const staggerContainer = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.12, delayChildren: 0.1 },
  },
};

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1] },
  },
};

const slideIn = {
  hidden: { opacity: 0, x: -16 },
  visible: {
    opacity: 1,
    x: 0,
    transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] },
  },
};

/* ─── helpers ─── */
function toBase64Payload(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      const base64 = result.split(",")[1];
      resolve(base64);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function deduplicateLogs(logs: string[]): string[] {
  return Array.from(new Set(logs));
}

/* ═══════════════════════════════════════════════════════════════
   ApothecaryDashboard
   ═══════════════════════════════════════════════════════════════ */
export default function ApothecaryDashboard({ apiUrl }: { apiUrl: string }) {
  /* ── state ── */
  const [rawText, setRawText] = useState("Augmentin 625 Tab BD");
  const [prescriberId, setPrescriberId] = useState("dr-1");
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<ExtractionResponse | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  /* ── file handling ── */
  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0] ?? null;
    setFile(f);
    setError(null);
  };

  const handleDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    const f = e.dataTransfer.files?.[0] ?? null;
    if (f && f.type.startsWith("image/")) {
      setFile(f);
      setError(null);
    }
  }, []);

  const handleDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const removeFile = () => {
    setFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  /* ── submit ── */
  const handleSubmit = async () => {
    setIsLoading(true);
    setError(null);
    setResponse(null);

    try {
      let imageBase64: string | null = null;
      if (file) {
        imageBase64 = await toBase64Payload(file);
      }

      const body: Record<string, string | null> = {
        image_base64: imageBase64,
        raw_text: rawText.trim() || null,
        prescriber_id: prescriberId.trim() || null,
      };

      const res = await fetch(`${apiUrl}/extract`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        throw new Error(errBody.detail ?? `Server error ${res.status}`);
      }

      const data: ExtractionResponse = await res.json();
      setResponse(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error occurred");
    } finally {
      setIsLoading(false);
    }
  };

  /* ── derived data ── */
  const medicine: ProcessedMedicine | null = response?.medicines?.[0] ?? null;
  const allGuardrailLogs = deduplicateLogs([
    ...(response?.guardrail_logs ?? []),
    ...(medicine?.guardrail_logs ?? []),
  ]);
  const scorePercent = medicine
    ? Math.round(medicine.matched_medicine.final_similarity_score * 100)
    : 0;

  /* ═══════════════════════════════════════════════════════════
     RENDER
     ═══════════════════════════════════════════════════════════ */
  return (
    <div className="flex min-h-screen flex-col bg-parchment">
      {/* ────────────────── HEADER ────────────────── */}
      <motion.header
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="sticky top-0 z-50 border-b border-rule bg-cream/90 backdrop-blur-md"
      >
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          {/* Left: logo */}
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full border border-gold-light bg-gradient-to-br from-gold-light to-parchment-warm">
              <Pill className="h-5 w-5 text-gold" strokeWidth={2.2} />
            </div>
            <div>
              <h1 className="font-display text-xl font-bold tracking-tight text-ink">
                MedMap AI
              </h1>
              <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-ink-muted">
                Pharmaceutical Ledger
              </p>
            </div>
          </div>

          {/* Right: status seal */}
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-ink-muted">System</span>
            <div
              className={`stamp-seal flex h-8 w-8 items-center justify-center ${
                isLoading ? "!border-gold" : "!border-verified"
              }`}
            >
              <span
                className={`block h-3 w-3 rounded-full ${
                  isLoading
                    ? "animate-pulse bg-gold"
                    : "bg-verified"
                }`}
              />
            </div>
          </div>
        </div>
      </motion.header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-6 pb-20 pt-8">
        <motion.div
          variants={staggerContainer}
          initial="hidden"
          animate="visible"
        >
          {/* ────────────────── HERO TAGLINE ────────────────── */}
          <motion.div variants={fadeUp} className="mb-10">
            <div className="ornament-divider">
              <span className="font-display text-sm italic text-ink-faint">
                Deterministic Clinical Intelligence
              </span>
            </div>
          </motion.div>

          {/* ────────────────── INPUT SECTION ────────────────── */}
          <motion.section
            variants={fadeUp}
            className="paper-card-elevated mb-10 rounded-xl p-6"
          >
            <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
              {/* LEFT: Rx textarea */}
              <div className="flex flex-col">
                <label className="mb-2 flex items-center gap-2.5 text-xs font-semibold uppercase tracking-widest text-ink-muted">
                  <span className="font-display text-2xl font-bold leading-none text-ink">Rx</span>
                  Prescription Text
                </label>
                <div className="flex flex-1 flex-col bg-ledger-texture ledger-margin rounded-lg border border-rule-light">
                  <textarea
                    value={rawText}
                    onChange={(e) => setRawText(e.target.value)}
                    rows={6}
                    placeholder="Enter prescription text…"
                    className="min-h-[180px] w-full flex-1 resize-none bg-transparent px-4 py-3 font-code text-sm leading-8 text-ink placeholder:text-ink-ghost focus:outline-none"
                  />
                </div>
              </div>

              {/* RIGHT: File upload */}
              <div className="flex flex-col">
                <label className="mb-2 flex items-center gap-2.5 text-xs font-semibold uppercase tracking-widest text-ink-muted">
                  <FileText className="h-4 w-4" />
                  Attach Specimen
                </label>

                {!file ? (
                  <div
                    onDrop={handleDrop}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onClick={() => fileInputRef.current?.click()}
                    className={`flex min-h-[180px] flex-1 cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed transition-colors ${
                      isDragging
                        ? "border-gold bg-gold-light/30"
                        : "border-rule-light bg-parchment-deep/40 hover:border-gold-light hover:bg-parchment-deep/60"
                    }`}
                  >
                    <Upload
                      className={`mb-2 h-8 w-8 ${
                        isDragging ? "text-gold" : "text-ink-ghost"
                      }`}
                    />
                    <p className="text-xs font-medium text-ink-muted">
                      Drop prescription image or{" "}
                      <span className="text-gold underline">browse</span>
                    </p>
                    <p className="mt-1 text-[10px] text-ink-ghost">
                      PNG, JPG, WEBP — max 10 MB
                    </p>
                  </div>
                ) : (
                  <div className="flex min-h-[180px] flex-1 flex-col items-center justify-center gap-2 rounded-lg border border-verified-light bg-verified-bg/50 p-4">
                    <CheckCircle2 className="h-8 w-8 text-verified" />
                    <p className="max-w-full truncate text-sm font-medium text-verified">
                      {file.name}
                    </p>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        removeFile();
                      }}
                      className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-alert hover:bg-alert-bg"
                    >
                      <X className="h-3 w-3" /> Remove
                    </button>
                  </div>
                )}

                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handleFileChange}
                  className="hidden"
                />
              </div>
            </div>

            {/* Bottom row: prescriber + submit */}
            <div className="mt-6 flex items-center gap-4 border-t border-rule-light pt-5">
              <div className="flex items-center gap-3">
                <label className="text-[10px] font-semibold uppercase tracking-widest text-ink-muted whitespace-nowrap">
                  Prescriber ID
                </label>
                <input
                  type="text"
                  value={prescriberId}
                  onChange={(e) => setPrescriberId(e.target.value)}
                  className="w-[180px] rounded-md border border-rule bg-cream px-3 py-2 font-code text-sm text-ink focus:border-gold focus:outline-none focus:ring-1 focus:ring-gold-light"
                />
              </div>

              <div className="flex-1" />

              <button
                onClick={handleSubmit}
                disabled={isLoading || (!rawText.trim() && !file)}
                className="group flex shrink-0 items-center gap-2 rounded-lg bg-gradient-to-r from-gold to-gold-shimmer px-6 py-2.5 font-display text-sm font-semibold text-cream shadow-md transition-all hover:shadow-lg hover:brightness-105 disabled:opacity-50 disabled:saturate-50"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Analyzing…
                  </>
                ) : (
                  <>
                    <Feather className="h-4 w-4 transition-transform group-hover:-rotate-6" />
                    Dispense Analysis
                  </>
                )}
              </button>
            </div>
          </motion.section>

          {/* ────────────────── ERROR ────────────────── */}
          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                className="mb-8 flex items-start gap-3 rounded-lg border border-alert-light bg-alert-bg p-4"
              >
                <AlertTriangle className="mt-0.5 h-5 w-5 flex-shrink-0 text-alert" />
                <div>
                  <p className="font-display text-sm font-semibold text-alert">
                    Dispensation Error
                  </p>
                  <p className="mt-1 text-sm text-alert/80">{error}</p>
                </div>
                <button
                  onClick={() => setError(null)}
                  className="ml-auto text-alert/60 hover:text-alert"
                >
                  <X className="h-4 w-4" />
                </button>
              </motion.div>
            )}
          </AnimatePresence>

          {/* ────────────────── LOADING ────────────────── */}
          <AnimatePresence>
            {isLoading && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="mb-10 flex flex-col items-center gap-4 py-12"
              >
                <Feather className="animate-quill h-10 w-10 text-gold" />
                <p className="font-display text-lg italic text-ink-muted">
                  Consulting the ledger…
                </p>
                <div className="h-1 w-48 overflow-hidden rounded-full bg-parchment-deep">
                  <motion.div
                    className="h-full rounded-full bg-gradient-to-r from-gold to-gold-shimmer"
                    animate={{ x: ["-100%", "100%"] }}
                    transition={{
                      repeat: Infinity,
                      duration: 1.5,
                      ease: "easeInOut",
                    }}
                    style={{ width: "50%" }}
                  />
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* ────────────────── RESULTS ────────────────── */}
          <AnimatePresence>
            {medicine && !isLoading && (
              <motion.div
                initial="hidden"
                animate="visible"
                variants={staggerContainer}
              >
                {/* Two-column layout */}
                <div className="grid gap-6 lg:grid-cols-2">
                  {/* ─── LEFT: Raw Appraisal ─── */}
                  <motion.div
                    variants={fadeUp}
                    className="paper-card rounded-xl border-l-4 border-l-alert p-6"
                  >
                    {/* Header */}
                    <div className="mb-4 flex items-center gap-3">
                      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-alert">
                        <FlaskConical className="h-3.5 w-3.5 text-cream" />
                      </span>
                      <h2 className="font-display text-base font-semibold text-ink">
                        Raw Appraisal{" "}
                        <span className="text-ink-muted">
                          — Unverified Extraction
                        </span>
                      </h2>
                    </div>

                    {/* CAUTION stamp */}
                    <div className="mb-4 flex items-center gap-2 rounded-md border border-alert-light bg-alert-bg px-3 py-2">
                      <AlertTriangle className="h-4 w-4 text-alert" />
                      <p className="text-xs font-semibold uppercase tracking-wider text-alert">
                        Caution — AI Hallucination Risk
                      </p>
                    </div>

                    {/* Flagged Token */}
                    {medicine.extracted.variant && (
                      <div className="mb-4">
                        <p className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-ink-muted">
                          Flagged Token
                        </p>
                        <span className="inline-flex items-center gap-1 rounded-md border border-alert bg-alert/10 px-2.5 py-1 font-code text-sm font-semibold text-alert">
                          <AlertTriangle className="h-3 w-3" />
                          {medicine.extracted.variant}
                        </span>
                      </div>
                    )}

                    {/* Raw JSON */}
                    <div>
                      <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-ink-muted">
                        Extracted Payload
                      </p>
                      <pre className="overflow-x-auto rounded-lg border border-rule-light bg-parchment-deep p-4 font-code text-xs leading-relaxed text-ink-soft">
                        {JSON.stringify(medicine.extracted, null, 2)}
                      </pre>
                    </div>
                  </motion.div>

                  {/* ─── RIGHT: Verified Dispensation ─── */}
                  <motion.div
                    variants={fadeUp}
                    className="paper-card rounded-xl border-l-4 border-l-verified p-6"
                  >
                    {/* Header */}
                    <div className="mb-4 flex items-center gap-3">
                      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-verified">
                        <CheckCircle2 className="h-3.5 w-3.5 text-cream" />
                      </span>
                      <h2 className="font-display text-base font-semibold text-ink">
                        Verified Dispensation{" "}
                        <span className="text-ink-muted">
                          — Ground Truth Locked
                        </span>
                      </h2>
                    </div>

                    {/* Confidence thermometer */}
                    <div className="mb-5">
                      <div className="mb-1 flex items-baseline justify-between">
                        <span className="text-[10px] font-semibold uppercase tracking-widest text-ink-muted">
                          Match Confidence
                        </span>
                        <span className="font-display text-2xl font-bold text-gold">
                          {scorePercent}%
                        </span>
                      </div>
                      <div className="h-3 w-full overflow-hidden rounded-full bg-parchment-deep">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${scorePercent}%` }}
                          transition={{ duration: 1, ease: "easeOut", delay: 0.3 }}
                          className="h-full rounded-full bg-gradient-to-r from-gold to-gold-shimmer"
                        />
                      </div>
                    </div>

                    {/* Ledger Table */}
                    <div className="overflow-hidden rounded-lg border border-rule">
                      <table className="w-full text-sm">
                        <tbody>
                          <LedgerRow
                            label="Brand Name"
                            value={medicine.matched_medicine.brand_name}
                          />
                          <LedgerRow
                            label="Variant"
                            value={medicine.extracted.variant ?? "—"}
                            even
                          />
                          <LedgerRow
                            label="Generic Backbone"
                            value={medicine.matched_medicine.generic_name}
                          />
                          <LedgerRow
                            label="Physical Form"
                            value={medicine.matched_medicine.form}
                            even
                          />
                          {/* Strength — full width highlight */}
                          <tr className="bg-verified-bg">
                            <td
                              colSpan={2}
                              className="px-4 py-3"
                            >
                              <div className="flex items-center justify-between">
                                <span className="text-xs font-semibold uppercase tracking-wider text-verified">
                                  Official Strength
                                </span>
                                <span className="font-display text-base font-bold text-verified">
                                  {medicine.matched_medicine.official_strength}
                                </span>
                              </div>
                            </td>
                          </tr>
                          {/* Combination Lock */}
                          <tr className="border-t border-rule-light">
                            <td className="px-4 py-3 text-xs font-medium text-ink-muted">
                              <div className="flex items-center gap-1.5">
                                <Lock className="h-3.5 w-3.5" />
                                Combination Lock
                              </div>
                            </td>
                            <td className="px-4 py-3 text-right">
                              <span
                                className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-semibold ${
                                  medicine.matched_medicine.combination_flag
                                    ? "bg-caution-bg text-caution-warm"
                                    : "bg-parchment-deep text-ink-muted"
                                }`}
                              >
                                <Lock className="h-3 w-3" />
                                {medicine.matched_medicine.combination_flag
                                  ? "LOCKED — Combination Product"
                                  : "Single Entity"}
                              </span>
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>

                    {/* Status stamp */}
                    <div className="mt-5 flex items-center justify-end gap-3">
                      {medicine.matched_medicine.manual_review_required ? (
                        <span className="inline-flex items-center gap-1.5 rounded-md border border-alert bg-alert-bg px-3 py-1.5 text-xs font-bold uppercase tracking-wider text-alert">
                          <AlertTriangle className="h-3.5 w-3.5" />
                          Review Required
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 rounded-md border border-verified bg-verified-bg px-3 py-1.5 text-xs font-bold uppercase tracking-wider text-verified">
                          <CheckCircle2 className="h-3.5 w-3.5" />
                          Verified ✓
                        </span>
                      )}

                      <RiskBadge tier={medicine.matched_medicine.clinical_risk_tier} />
                    </div>
                  </motion.div>
                </div>

                {/* ────────────────── GUARDRAIL AUDIT LEDGER ────────────────── */}
                {allGuardrailLogs.length > 0 && (
                  <motion.section
                    variants={fadeUp}
                    className="paper-card mt-8 rounded-xl p-6"
                  >
                    <div className="mb-5 flex items-center gap-3">
                      <Shield className="h-5 w-5 text-gold" />
                      <h2 className="font-display text-base font-semibold text-ink">
                        Audit Ledger
                      </h2>
                      <span className="inline-flex h-5 min-w-[20px] items-center justify-center rounded-full bg-gold px-1.5 text-[10px] font-bold text-cream">
                        {allGuardrailLogs.length}
                      </span>
                    </div>

                    <div className="overflow-hidden rounded-lg border border-rule">
                      {allGuardrailLogs.map((log, i) => (
                        <motion.div
                          key={`${log}-${i}`}
                          variants={slideIn}
                          initial="hidden"
                          animate="visible"
                          transition={{ delay: i * 0.06 }}
                          className={`flex items-start gap-3 border-l-2 border-l-gold-light px-4 py-3 ${
                            i % 2 === 0
                              ? "bg-cream"
                              : "bg-parchment-deep"
                          } ${
                            i < allGuardrailLogs.length - 1
                              ? "border-b border-b-rule-light"
                              : ""
                          }`}
                        >
                          <span className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-gold text-[10px] font-bold text-cream">
                            {i + 1}
                          </span>
                          <p className="text-sm leading-relaxed text-ink-soft">
                            {log}
                          </p>
                        </motion.div>
                      ))}
                    </div>
                  </motion.section>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      </main>

      {/* Footer */}
      <footer className="mt-auto border-t border-rule-light py-6 text-center">
        <p className="text-xs text-ink-ghost">
          MedMap AI · Apothecary Ledger v2 ·{" "}
          <span className="font-code">Deterministic XAI Pipeline</span>
        </p>
      </footer>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   Sub-components
   ═══════════════════════════════════════════════════════════════ */

function LedgerRow({
  label,
  value,
  even = false,
}: {
  label: string;
  value: string;
  even?: boolean;
}) {
  return (
    <tr
      className={`border-b border-rule-light ${
        even ? "bg-parchment-deep/50" : "bg-cream"
      }`}
    >
      <td className="px-4 py-2.5 text-xs font-medium text-ink-muted">
        {label}
      </td>
      <td className="px-4 py-2.5 text-right font-medium text-ink">
        {value}
      </td>
    </tr>
  );
}

function RiskBadge({ tier }: { tier: "High" | "Medium" | "Low" }) {
  const styles: Record<string, string> = {
    High: "border-alert bg-alert-bg text-alert",
    Medium: "border-caution-warm bg-caution-bg text-caution-warm",
    Low: "border-verified bg-verified-bg text-verified",
  };

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md border px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider ${styles[tier]}`}
    >
      Risk: {tier}
    </span>
  );
}
