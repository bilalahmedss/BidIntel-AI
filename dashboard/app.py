import os
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

import sys
from pathlib import Path
import tempfile
import json
import datetime

project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import streamlit as st
import pdfplumber

from ingestion.rfp_parser import parse_rfp_pdf
from scoring.poison_pill import detect_poison_pills
from scoring.criterion_scorer import score_extracted_gates
from rag.retriever import retrieve
from scoring.wps_calculator import calculate_wps


def extract_raw_pages(pdf_path: str):
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            pages.append({"page_number": i, "text": page.extract_text() or ""})
    return pages


def verdict_color(verdict: str) -> str:
    if verdict == "DO NOT BID":
        return "red"
    if verdict == "Weak Bid":
        return "orange"
    if verdict == "Borderline Bid":
        return "yellow"
    if verdict == "Competitive Bid":
        return "blue"
    if verdict == "Strong Bid":
        return "green"
    return "gray"


def main():
    st.set_page_config(page_title="BidIntel AI", layout="wide")
    st.title("BidIntel AI — Tender Decision Engine")
    st.caption("Upload a tender PDF and your company documents to get a go/no-go decision.")

    st.sidebar.header("Upload Documents")
    tender_file = st.sidebar.file_uploader("Tender PDF", type=["pdf"])
    brain_files = st.sidebar.file_uploader(
        "Company Brain Documents",
        type=["txt", "pdf", "docx"],
        accept_multiple_files=True
    )
    run = st.sidebar.button("Run Analysis", type="primary")

    if run:
        if not tender_file:
            st.error("Please upload a tender PDF first.")
            return

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(tender_file.read())
            pdf_path = tmp.name

        try:
            with st.status("Running analysis...", expanded=True) as status:

                st.write("Parsing tender document...")
                parsed = parse_rfp_pdf(pdf_path)
                gates = parsed.get("gates", [])
                extracted_pills = parsed.get("poison_pill_clauses", [])

                st.write("Detecting poison pill clauses...")
                raw_pages = extract_raw_pages(pdf_path)
                poison_pills = detect_poison_pills(
                    extracted_poison_pills=extracted_pills,
                    raw_pages=raw_pages
                )

                st.write("Scoring criteria against company brain...")
                scoring_result = score_extracted_gates(gates, retrieve, top_k=3)
                criterion_results = scoring_result.get("criterion_results", [])

                st.write("Calculating Win Probability Score...")
                wps_results = {}
                for scenario in ["conservative", "expected", "optimistic"]:
                    wps_results[scenario] = calculate_wps(
                        gates, criterion_results, financial_scenario=scenario
                    )

                st.session_state.wps_results = wps_results
                st.session_state.criterion_results = criterion_results
                st.session_state.poison_pills = poison_pills

                status.update(label="Analysis complete.", state="complete")

        except Exception as e:
            st.error(f"Something went wrong: {e}")
            import traceback
            st.code(traceback.format_exc())
            return
        finally:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)

        out_dir = Path(project_root) / "data" / "outputs"
        out_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        with open(out_dir / f"scorer_results_{timestamp}.json", "w", encoding="utf-8") as f:
            json.dump(criterion_results, f, indent=2)
            
        with open(out_dir / f"poison_pill_results_{timestamp}.json", "w", encoding="utf-8") as f:
            json.dump(poison_pills, f, indent=2)
            
        with open(out_dir / f"wps_results_{timestamp}.json", "w", encoding="utf-8") as f:
            json.dump(wps_results, f, indent=2)

    if ("wps_results" not in st.session_state or 
        "criterion_results" not in st.session_state or 
        "poison_pills" not in st.session_state):
        st.info("Upload a tender PDF and your company documents, then click Run Analysis.")
        return

    wps_results = st.session_state.wps_results
    criterion_results = st.session_state.criterion_results
    poison_pills = st.session_state.poison_pills

    scenario = st.selectbox(
        "Financial Scenario",
        ["expected", "conservative", "optimistic"]
    )

    tab1, tab2, tab3 = st.tabs(["WPS Summary", "Criterion Breakdown", "Poison Pill Report"])

    with tab1:
        st.header("Win Probability Score")

        result = wps_results[scenario]
        verdict = result.get("verdict", "N/A")
        constraint = result.get("binding_constraint", "N/A")
        scenarios = result.get("scenarios", {})
        current = scenarios.get(scenario, {})
        wps = current.get("wps", 0.0)

        col1, col2, col3 = st.columns(3)
        col1.metric("WPS", f"{wps:.1f} / 100")
        col2.metric("Verdict", verdict)
        col3.metric("Binding Constraint", constraint)

        st.divider()
        st.subheader("All Scenarios")
        cols = st.columns(3)
        for i, s in enumerate(["conservative", "expected", "optimistic"]):
            val = wps_results[s].get("scenarios", {}).get(s, {}).get("wps", 0.0)
            verd = wps_results[s].get("verdict", "N/A")
            cols[i].metric(s.capitalize(), f"{val:.1f}", verd)

    with tab2:
        st.header("Criterion Breakdown")

        for item in criterion_results:
            gate = item.get("gate_name", "")
            name = item.get("name", "N/A")
            status_val = item.get("status", "N/A")
            matched = item.get("matched_signals", [])
            gaps = item.get("gap_signals", [])
            score = item.get("score")
            max_pts = item.get("max_points")

            if status_val == "PASS" or status_val == "PRESENT":
                icon = "✅"
            elif status_val == "FAIL" or status_val == "MISSING":
                icon = "❌"
            else:
                icon = "⚠️"

            label = f"{icon} [{gate}] {name}"
            if score is not None:
                label += f" — {score}/{max_pts} pts"

            with st.expander(label):
                if matched:
                    st.markdown("**Matched Signals**")
                    for s in matched:
                        st.markdown(f"- {s}")
                if gaps:
                    st.markdown("**Gap Signals**")
                    for g in gaps:
                        st.markdown(f"- ⚠️ {g}")
                if not matched and not gaps:
                    st.write("No signals extracted.")

    with tab3:
        st.header("Poison Pill Report")

        if not poison_pills:
            st.success("No poison pill clauses detected.")
        else:
            critical = [p for p in poison_pills if p.get("severity") == "CRITICAL"]
            high = [p for p in poison_pills if p.get("severity") == "HIGH"]
            medium = [p for p in poison_pills if p.get("severity") == "MEDIUM"]

            st.metric("Total Flagged", len(poison_pills))

            col1, col2, col3 = st.columns(3)
            col1.metric("Critical", len(critical))
            col2.metric("High", len(high))
            col3.metric("Medium", len(medium))

            st.divider()

            for severity, group in [("CRITICAL", critical), ("HIGH", high), ("MEDIUM", medium)]:
                if not group:
                    continue
                st.subheader(f"{severity} ({len(group)})")
                for pp in group:
                    with st.expander(f"Page {pp.get('page_number', '?')} — {pp.get('reason', '')}"):
                        st.write(pp.get("clause_text", ""))
                        st.caption(f"Source: {pp.get('source', 'unknown')}")


if __name__ == "__main__":
    main()


# cd F:\Sem8\GenAi\Project\bidintel
# .\.venv\Scripts\python.exe -m streamlit run dashboard\app.py --logger.level=error

# Conservative: assumes you're pricing 30% above the lowest competitor. You get a lower financial score. This is the worst realistic case, useful if you know your firm tends to price high.
# Expected: assumes you're pricing 10% above the lowest competitor. Middle ground. Most realistic for a competitive but not cheapest bid.
# Optimistic: assumes you're the lowest bidder. You get the maximum financial points. Best case scenario.