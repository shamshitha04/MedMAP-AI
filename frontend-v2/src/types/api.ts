export interface ExtractedData {
	raw_input: string;
	brand: string;
	variant?: string | null;
	generic_name?: string | null;
	strength?: string | null;
	form?: string | null;
	frequency?: string | null;
}

export interface MatchedMedicine {
	id: number;
	brand_name: string;
	generic_name: string;
	official_strength: string;
	form: string;
	combination_flag: boolean;
	final_similarity_score: number;
	risk_classification: "High" | "Medium" | "Low";
	clinical_risk_tier: "High" | "Medium" | "Low";
	manual_review_required: boolean;
}

export interface ProcessedMedicine {
	original_raw_input: string;
	extracted: ExtractedData;
	matched_medicine: MatchedMedicine;
	guardrail_logs: string[];
}

export interface ExtractionResponse {
	medicines: ProcessedMedicine[];
	guardrail_logs: string[];
}
