import ClinicalDashboard from "../components/custom/ClinicalDashboard";

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/extract";

export default function Home() {
	return <ClinicalDashboard apiUrl={apiUrl} />;
}

