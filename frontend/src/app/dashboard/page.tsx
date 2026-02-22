import ClinicalDashboard from "../../components/custom/ClinicalDashboard";

const apiUrl = "http://127.0.0.1:8000/extract";

export default function DashboardPage() {
	return <ClinicalDashboard apiUrl={apiUrl} />;
}
