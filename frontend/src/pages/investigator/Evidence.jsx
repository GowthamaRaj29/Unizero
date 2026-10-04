import { FileText, Upload } from "lucide-react";
import { useEffect, useState } from "react";
import PageHeader from "../../components/PageHeader";
import {
  getEvidence,
  getInvestigations,
  uploadEvidence,
} from "../../services/investigationApi";

function Evidence() {
  const [investigations, setInvestigations] = useState([]);
  const [evidence, setEvidence] = useState([]);
  const [selectedInvestigation, setSelectedInvestigation] = useState("");
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  const loadEvidence = async (items = investigations) => {
    const records = await Promise.all(
      items.map(async (investigation) => {
        const files = await getEvidence(investigation.id);
        return files.map((file) => ({
          ...file,
          break_id: investigation.break_id,
        }));
      })
    );
    setEvidence(records.flat());
  };

  useEffect(() => {
    getInvestigations()
      .then(async (items) => {
        const records = Array.isArray(items) ? items : [];
        setInvestigations(records);
        setSelectedInvestigation(records[0]?.id || "");
        await loadEvidence(records);
      })
      .catch((requestError) => setError(requestError.message || "Unable to load evidence."))
      .finally(() => setLoading(false));
  }, []);

  async function handleUpload(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || !selectedInvestigation) {
      setError("Select an investigation before uploading evidence.");
      return;
    }

    setUploading(true);
    setError("");
    try {
      await uploadEvidence(selectedInvestigation, file);
      await loadEvidence();
    } catch (uploadError) {
      setError(uploadError.message || "Unable to upload evidence.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="w-full max-w-[1500px] mx-auto text-white">
      <PageHeader
        eyebrow="INVESTIGATION"
        title="Evidence"
        description="Review supporting evidence attached to persisted investigations."
        action={
          <label className="flex cursor-pointer items-center gap-2 rounded-xl border border-[#1e815b] bg-[#0b3021] px-5 py-3 text-sm font-semibold text-[#39df99]">
            <Upload size={17} />
            {uploading ? "Uploading..." : "Upload Evidence"}
            <input type="file" className="sr-only" onChange={handleUpload} disabled={uploading} />
          </label>
        }
      />

      {error && <div className="mb-5 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</div>}

      <div className="mb-5 rounded-2xl border border-[#153d30] bg-[#071b14] p-5">
        <label htmlFor="evidence-investigation" className="mb-2 block text-sm font-medium text-[#91aaa0]">
          Investigation
        </label>
        <select
          id="evidence-investigation"
          value={selectedInvestigation}
          onChange={(event) => setSelectedInvestigation(event.target.value)}
          className="w-full rounded-xl border border-[#153d30] bg-[#041710] px-4 py-3 text-sm text-white outline-none"
        >
          <option value="">Select an investigation</option>
          {investigations.map((investigation) => (
            <option key={investigation.id} value={investigation.id}>
              {investigation.id} · Break {investigation.break_id}
            </option>
          ))}
        </select>
      </div>

      <div className="overflow-hidden rounded-2xl border border-[#153d30] bg-[#071b14]">
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-[#153d30] text-xs uppercase tracking-wider text-[#52786a]">
              <th className="px-5 py-4">File</th>
              <th className="px-5 py-4">Investigation</th>
              <th className="px-5 py-4">Break</th>
              <th className="px-5 py-4">Size</th>
              <th className="px-5 py-4">Uploaded</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan="5" className="px-5 py-12 text-center text-sm text-[#729487]">Loading evidence...</td></tr>
            ) : evidence.length === 0 ? (
              <tr><td colSpan="5" className="px-5 py-12 text-center text-sm text-[#729487]">No evidence has been uploaded.</td></tr>
            ) : evidence.map((item) => (
              <tr key={item.id} className="border-b border-[#102e24]">
                <td className="px-5 py-4"><span className="flex items-center gap-2 text-sm text-white"><FileText size={16} className="text-[#39df99]" />{item.filename}</span></td>
                <td className="px-5 py-4 text-sm text-[#91aaa0]">{item.investigation_id}</td>
                <td className="px-5 py-4 text-sm text-[#91aaa0]">{item.break_id || "—"}</td>
                <td className="px-5 py-4 text-sm text-[#91aaa0]">{item.size} bytes</td>
                <td className="px-5 py-4 text-sm text-[#91aaa0]">{item.created_at || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default Evidence;
