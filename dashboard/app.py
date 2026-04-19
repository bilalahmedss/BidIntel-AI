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

import time

import streamlit as st
import pdfplumber

from ingestion.rfp_parser import parse_rfp_pdf
from ingestion.response_loader import build_response_index
from scoring.poison_pill import detect_poison_pills
from scoring.criterion_scorer import score_extracted_gates
from rag.retriever import make_retriever
from scoring.wps_calculator import calculate_wps


def extract_raw_pages(pdf_path: str):
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            pages.append({"page_number": i, "text": page.extract_text() or ""})
    return pages


def verdict_color(verdict: str) -> str:
    colors = {
        "DO NOT BID": "red",
        "Weak Bid": "orange",
        "Borderline Bid": "yellow",
        "Competitive Bid": "blue",
        "Strong Bid": "green",
    }
    return colors.get(verdict, "gray")


def main():
    st.set_page_config(page_title="BidIntel AI", layout="wide")
    st.title("BidIntel AI — RFP Response Evaluator")
    st.caption(
        "Upload the tender/RFP and your bid response. "
        "The system scores how well your response addresses every requirement."
    )

    st.sidebar.header("Upload Documents")
    tender_file = st.sidebar.file_uploader("Tender / RFP PDF", type=["pdf"])
    response_file = st.sidebar.file_uploader(
        "Your Bid Response PDF",
        type=["pdf"],
        help="Upload the response document you submitted (or plan to submit) for this tender.",
    )
    run = st.sidebar.button("Run Analysis", type="primary")

    if run:
        if not tender_file:
            st.error("Please upload the tender / RFP PDF.")
            return
        if not response_file:
            st.error("Please upload your bid response PDF.")
            return

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_rfp:
            tmp_rfp.write(tender_file.read())
            rfp_path = tmp_rfp.name

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_resp:
            tmp_resp.write(response_file.read())
            response_path = tmp_resp.name

        try:
            start_time = time.time()

            progress_bar = st.progress(0)
            step_label = st.empty()
            timer_label = st.empty()
            detail_label = st.empty()

            def set_step(pct: int, label: str, detail: str = ""):
                elapsed = time.time() - start_time
                progress_bar.progress(pct)
                step_label.markdown(f"**{label}**")
                timer_label.caption(f"Elapsed: {elapsed:.1f}s")
                if detail:
                    detail_label.caption(detail)
                else:
                    detail_label.empty()

            set_step(2, "Starting analysis...")

            # Pre-count chunks so the callback can show X/N
            import pdfplumber as _plumber
            with _plumber.open(rfp_path) as _pdf:
                _page_count = len(_pdf.pages)
            _estimated_chunks = max(1, _page_count // 10 + 1)

            def on_chunk_progress(current: int, total: int):
                elapsed = time.time() - start_time
                pct = 5 + int((current / max(total, 1)) * 18)
                progress_bar.progress(pct)
                step_label.markdown(
                    f"**Step 1 / 5 — Parsing tender document** (chunk {current}/{total})"
                )
                timer_label.caption(f"Elapsed: {elapsed:.1f}s")
                detail_label.caption(
                    f"Sending chunk {current} of {total} to LLM — extracting gates, criteria and scoring rules..."
                )

            set_step(5, f"Step 1 / 5 — Parsing tender document (~{_estimated_chunks} chunks)",
                     "Sending RFP chunks to LLM to extract gates, criteria and scoring rules...")
            parsed = parse_rfp_pdf(rfp_path, on_chunk_progress=on_chunk_progress)
            gates = parsed.get("gates", [])
            extracted_pills = parsed.get("poison_pill_clauses", [])
            total_criteria = sum(len(g.get("criteria", [])) for g in gates)

            set_step(25, "Step 2 / 5 — Detecting poison pill clauses",
                     "Scanning tender pages for risky or disqualifying contract terms...")
            raw_pages = extract_raw_pages(rfp_path)
            poison_pills = detect_poison_pills(
                extracted_poison_pills=extracted_pills,
                raw_pages=raw_pages,
            )

            set_step(40, "Step 3 / 5 — Indexing your bid response",
                     "Loading embedding model and building semantic index from your response PDF...")
            response_index = build_response_index(response_path)
            retriever = make_retriever(response_index)

            # Criterion scoring — most time-consuming step, track per criterion
            # Each criterion = one LLM call
            scoring_placeholder = st.empty()
            criteria_done = [0]

            def on_criterion_progress(current: int, total: int, name: str):
                criteria_done[0] = current
                pct = 50 + int((current / max(total, 1)) * 38)
                elapsed = time.time() - start_time
                progress_bar.progress(pct)
                step_label.markdown(
                    f"**Step 4 / 5 — Scoring criteria against your response** "
                    f"({current}/{total})"
                )
                timer_label.caption(f"Elapsed: {elapsed:.1f}s")
                detail_label.caption(f"Scoring: *{name}*")

            set_step(50, f"Step 4 / 5 — Scoring {total_criteria} criteria against your response",
                     "Retrieving relevant passages from your response and matching each requirement...")
            scoring_result = score_extracted_gates(
                gates, retriever, top_k=3, on_progress=on_criterion_progress
            )
            criterion_results = scoring_result.get("criterion_results", [])

            set_step(90, "Step 5 / 5 — Calculating Win Probability Score",
                     "Computing WPS across conservative, expected, and optimistic scenarios...")
            wps_results = {}
            for scenario in ["conservative", "expected", "optimistic"]:
                wps_results[scenario] = calculate_wps(
                    gates, criterion_results, financial_scenario=scenario
                )

            elapsed_total = time.time() - start_time
            progress_bar.progress(100)
            step_label.markdown("**Analysis complete.**")
            timer_label.caption(f"Finished in {elapsed_total:.1f}s")
            detail_label.empty()

            st.session_state.wps_results = wps_results
            st.session_state.criterion_results = criterion_results
            st.session_state.poison_pills = poison_pills
            st.session_state.rfp_meta = {
                "rfp_id": parsed.get("rfp_id", ""),
                "issuer": parsed.get("issuer", ""),
                "submission_rules": parsed.get("submission_rules", []),
            }

        except Exception as e:
            st.error(f"Something went wrong: {e}")
            import traceback
            st.code(traceback.format_exc())
            return
        finally:
            for path in (rfp_path, response_path):
                if os.path.exists(path):
                    os.remove(path)

        out_dir = Path(project_root) / "data" / "outputs"
        out_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        with open(out_dir / f"scorer_results_{timestamp}.json", "w", encoding="utf-8") as f:
            json.dump(criterion_results, f, indent=2)
        with open(out_dir / f"poison_pill_results_{timestamp}.json", "w", encoding="utf-8") as f:
            json.dump(poison_pills, f, indent=2)
        with open(out_dir / f"wps_results_{timestamp}.json", "w", encoding="utf-8") as f:
            json.dump(wps_results, f, indent=2)

    if (
        "wps_results" not in st.session_state
        or "criterion_results" not in st.session_state
        or "poison_pills" not in st.session_state
    ):
        st.info("Upload the tender PDF and your bid response PDF, then click **Run Analysis**.")
        return

    wps_results = st.session_state.wps_results
    criterion_results = st.session_state.criterion_results
    poison_pills = st.session_state.poison_pills
    rfp_meta = st.session_state.get("rfp_meta", {})

    if rfp_meta.get("issuer") or rfp_meta.get("rfp_id"):
        st.caption(
            f"Tender: **{rfp_meta.get('rfp_id', 'N/A')}** | Issuer: **{rfp_meta.get('issuer', 'N/A')}**"
        )

    scenario = st.selectbox("Financial Scenario", ["expected", "conservative", "optimistic"])

    tab1, tab2, tab3, tab4 = st.tabs(
        ["WPS Summary", "Criterion Breakdown", "Gap Analysis", "Poison Pill Report"]
    )

    with tab1:
        st.header("Win Probability Score")

        result = wps_results[scenario]
        verdict = result.get("verdict", "N/A")
        constraint = result.get("binding_constraint", "N/A")
        scenarios_data = result.get("scenarios", {})
        current = scenarios_data.get(scenario, {})
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

        if rfp_meta.get("submission_rules"):
            st.divider()
            st.subheader("Submission Rules")
            for rule in rfp_meta["submission_rules"]:
                st.markdown(f"- {rule}")

    with tab2:
        st.header("Criterion Breakdown")
        st.caption("Shows which RFP requirements your response addressed and how well.")

        for item in criterion_results:
            gate = item.get("gate_name", "")
            name = item.get("name", "N/A")
            status_val = item.get("status", "N/A")
            matched = item.get("matched_signals", [])
            gaps = item.get("gap_signals", [])
            score = item.get("score")
            max_pts = item.get("max_points")

            if status_val in ("PASS", "PRESENT"):
                icon = "✅"
            elif status_val in ("FAIL", "MISSING"):
                icon = "❌"
            else:
                icon = "⚠️"

            label = f"{icon} [{gate}] {name}"
            if score is not None:
                label += f" — {score}/{max_pts} pts"

            with st.expander(label):
                if matched:
                    st.markdown("**Evidence Found in Your Response**")
                    for s in matched:
                        st.markdown(f"- ✅ {s}")
                if gaps:
                    st.markdown("**Missing Requirements (Gap)**")
                    for g in gaps:
                        st.markdown(f"- ⚠️ {g}")
                if not matched and not gaps:
                    st.write("No signals extracted.")

    with tab3:
        st.header("Gap Analysis")
        st.caption(
            "Requirements from the tender that are **not addressed** in your bid response. "
            "These are the areas to strengthen before submission."
        )

        all_gaps = [
            (item.get("gate_name", ""), item.get("name", ""), g)
            for item in criterion_results
            for g in item.get("gap_signals", [])
        ]

        if not all_gaps:
            st.success("No gaps detected — your response appears to cover all extracted requirements.")
        else:
            st.warning(f"{len(all_gaps)} unaddressed requirement(s) found.")
            by_gate: dict = {}
            for gate_name, crit_name, gap in all_gaps:
                by_gate.setdefault(gate_name, []).append((crit_name, gap))

            for gate_name, items in by_gate.items():
                st.subheader(gate_name or "General")
                for crit_name, gap in items:
                    st.markdown(f"- **{crit_name}**: {gap}")

    with tab4:
        st.header("Poison Pill Report")
        st.caption("Risky or disqualifying clauses detected in the tender document.")

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
