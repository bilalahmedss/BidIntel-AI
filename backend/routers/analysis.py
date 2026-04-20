import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("bidintel.analysis")

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.database import get_db, row, rows
from backend.deps import get_current_user, get_current_user_from_token
from backend.safety import QuerySafetyLayer

router = APIRouter()

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "data" / "uploads"
_safety = QuerySafetyLayer()


@dataclass
class Job:
    job_id: str
    project_id: int
    status: str = "queued"
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    analysis_id: Optional[int] = None
    error: Optional[str] = None
    started_at: float = field(default_factory=time.time)


_jobs: dict[str, Job] = {}


class StartIn(BaseModel):
    project_id: int
    financial_scenario: str = "expected"


def _build_wps_explanation(
    scenario: str,
    selected: dict,
    criterion_results: list[dict],
    poison_pills: list[dict],
) -> str:
    total = len(criterion_results)
    met = sum(1 for item in criterion_results if item.get("status") in {"PRESENT", "PASS"})
    gaps = sum(len(item.get("gap_signals", [])) for item in criterion_results)
    severe_pills = [pill for pill in poison_pills if pill.get("severity") in {"CRITICAL", "HIGH"}]
    binding = selected.get("binding_constraint", "")
    parts = [
        f"In the {scenario} scenario, BidIntel marked {met} of {total or 0} requirements as met.",
    ]
    if gaps:
        parts.append(f"The response still shows {gaps} unresolved gap signal(s).")
    if severe_pills:
        parts.append(f"{len(severe_pills)} high-severity poison pill clause(s) increase delivery and legal risk.")
    if binding:
        parts.append(f"Primary scoring driver: {binding}.")
    return " ".join(parts)


async def _run_pipeline(job: Job, rfp_path: str, response_path: Optional[str], scenario: str):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    loop = asyncio.get_running_loop()

    def emit(event: dict):
        event.setdefault("elapsed_s", round(time.time() - job.started_at, 1))
        loop.call_soon_threadsafe(job.queue.put_nowait, event)

    # Yield immediately so the SSE stream can connect before we start blocking work
    await asyncio.sleep(0)

    try:
        job.status = "running"
        logger.info("[job=%s] Pipeline started | project=%s scenario=%s", job.job_id[:8], job.project_id, scenario)
        logger.info("[job=%s] RFP path: %s", job.job_id[:8], rfp_path)
        logger.info("[job=%s] Response path: %s (exists=%s)", job.job_id[:8], response_path, Path(response_path).exists() if response_path else False)
        db = get_db()
        db.execute("UPDATE analysis_jobs SET status='running', updated_at=datetime('now') WHERE job_id=?", (job.job_id,))
        db.commit()

        # Run heavy imports in a thread so they don't block the event loop
        def _do_imports():
            import importlib
            importlib.import_module("ingestion.rfp_parser")
            importlib.import_module("ingestion.response_loader")
            importlib.import_module("rag.retriever")
            importlib.import_module("scoring.poison_pill")
            importlib.import_module("scoring.criterion_scorer")
            importlib.import_module("scoring.wps_calculator")

        emit({"event": "progress", "step": 1, "total_steps": 5, "label": "Loading analysis modules…", "pct": 1})
        await asyncio.to_thread(_do_imports)

        from ingestion.rfp_parser import parse_rfp_pdf
        from ingestion.response_loader import build_response_index
        from ingestion.project_indexer import load_project_index, build_project_index
        from rag.retriever import make_retriever
        from scoring.poison_pill import detect_poison_pills
        from scoring.criterion_scorer import score_extracted_gates
        from scoring.wps_calculator import calculate_wps
        from ingestion.pdf_utils import extract_pdf_pages

        # Step 1 — Parse RFP
        def on_chunk_start(current, total):
            emit({"event": "progress", "step": 1, "total_steps": 5,
                  "label": f"Calling Groq API — RFP chunk {current}/{total}…",
                  "pct": 5 + int((current - 1) / max(total, 1) * 20)})

        def on_chunk_done(current, total):
            emit({"event": "progress", "step": 1, "total_steps": 5,
                  "label": f"Parsed RFP chunk {current}/{total}",
                  "pct": 5 + int(current / max(total, 1) * 20)})

        emit({"event": "progress", "step": 1, "total_steps": 5, "label": "Reading RFP PDF…", "pct": 3})
        logger.info("[job=%s] Step 1: Parsing RFP PDF", job.job_id[:8])
        parsed = await asyncio.to_thread(
            parse_rfp_pdf, rfp_path,
            on_chunk_progress=on_chunk_done,
            on_chunk_start=on_chunk_start,
        )
        gates = parsed.get("gates", [])
        pills_raw = parsed.get("poison_pill_clauses", [])
        logger.info("[job=%s] Step 1 done: %d gates, %d poison pill clauses extracted", job.job_id[:8], len(gates), len(pills_raw))

        # Cache parsed RFP in project
        db.execute("UPDATE projects SET parsed_rfp_json=?, updated_at=datetime('now') WHERE id=?",
                   (json.dumps(parsed), job.project_id))
        db.commit()

        # Step 2 — Poison pills
        emit({"event": "progress", "step": 2, "total_steps": 5, "label": "Detecting poison pill clauses…", "pct": 28})
        logger.info("[job=%s] Step 2: Detecting poison pills", job.job_id[:8])

        def _extract_pages(path):
            return extract_pdf_pages(path)

        raw_pages = await asyncio.to_thread(_extract_pages, rfp_path)
        poison_pills = await asyncio.to_thread(detect_poison_pills, pills_raw, raw_pages)
        logger.info("[job=%s] Step 2 done: %d poison pills detected", job.job_id[:8], len(poison_pills))

        # Step 3 — Index response + company brain
        BRAIN_DIR = Path(__file__).resolve().parents[2] / "data" / "company_brain"
        criterion_results = []
        has_response = response_path and Path(response_path).exists()
        has_brain = BRAIN_DIR.exists() and any(BRAIN_DIR.iterdir())
        logger.info("[job=%s] Step 3: has_response=%s has_brain=%s", job.job_id[:8], has_response, has_brain)

        if has_response or has_brain:
            retrievers = []
            if has_response:
                emit({"event": "progress", "step": 3, "total_steps": 5, "label": "Loading bid response index…", "pct": 40})
                response_index = await asyncio.to_thread(load_project_index, job.project_id, "response")
                if response_index is None:
                    # Index not ready yet — build it now as a fallback
                    emit({"event": "progress", "step": 3, "total_steps": 5, "label": "Building bid response index…", "pct": 40})
                    response_index = await asyncio.to_thread(build_project_index, job.project_id, response_path, "response")
                retrievers.append(make_retriever(response_index))
            if has_brain:
                emit({"event": "progress", "step": 3, "total_steps": 5, "label": "Loading company knowledge base…", "pct": 44})
                from ingestion.kb_loader import build_kb_index
                brain_index = await asyncio.to_thread(build_kb_index, str(BRAIN_DIR))
                retrievers.append(make_retriever(brain_index))

            def combined_retriever(query: str, top_k: int = 3):
                seen, results = set(), []
                for ret in retrievers:
                    for chunk in ret(query, top_k):
                        if chunk not in seen:
                            seen.add(chunk)
                            results.append(chunk)
                return results

            # Step 4 — Score criteria
            total_criteria = sum(len(g.get("criteria", [])) for g in gates)

            def on_criterion(current, total, name):
                pct = 50 + int(current / max(total, 1) * 38)
                emit({"event": "progress", "step": 4, "total_steps": 5,
                      "label": f"Scoring criteria ({current}/{total}): {name[:50]}",
                      "pct": pct})

            logger.info("[job=%s] Step 4: Scoring %d criteria across %d gates", job.job_id[:8], total_criteria, len(gates))
            emit({"event": "progress", "step": 4, "total_steps": 5,
                  "label": f"Scoring {total_criteria} criteria…", "pct": 50})
            scoring = await asyncio.to_thread(
                score_extracted_gates, gates, combined_retriever, 3, None, "llama-3.3-70b-versatile", on_criterion
            )
            criterion_results = scoring.get("criterion_results", [])
            present = sum(1 for c in criterion_results if c.get("status") == "PRESENT")
            logger.info("[job=%s] Step 4 done: %d/%d criteria PRESENT", job.job_id[:8], present, len(criterion_results))
        else:
            logger.warning("[job=%s] Step 3: No response PDF or knowledge base — skipping scoring", job.job_id[:8])
            emit({"event": "progress", "step": 3, "total_steps": 5,
                  "label": "No response PDF or knowledge base — skipping scoring", "pct": 50})

        # Step 5 — WPS
        emit({"event": "progress", "step": 5, "total_steps": 5, "label": "Calculating Win Probability Score…", "pct": 92})
        logger.info("[job=%s] Step 5: Calculating WPS", job.job_id[:8])
        wps_results = {}
        for s in ["conservative", "expected", "optimistic"]:
            wps_results[s] = calculate_wps(gates, criterion_results, financial_scenario=s)

        selected = wps_results[scenario]
        for s in ["conservative", "expected", "optimistic"]:
            wps_results[s]["scenarios"][s]["explanation"] = _build_wps_explanation(
                s, wps_results[s], criterion_results, poison_pills
            )
        logger.info("[job=%s] Step 5 done: verdict=%s wps=%.2f (scenario=%s) | constraint: %s",
                    job.job_id[:8], selected.get("verdict"),
                    selected.get("scenarios", {}).get(scenario, {}).get("wps", 0),
                    scenario, selected.get("binding_constraint", ""))

        # Store results
        cur = db.execute(
            """INSERT INTO analysis_results
               (job_id, project_id, financial_scenario, rfp_meta_json, gates_json,
                criterion_results_json, gate_results_json, wps_summary_json, scenarios_json, poison_pills_json)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                job.job_id, job.project_id, scenario,
                json.dumps({"rfp_id": parsed.get("rfp_id", ""), "issuer": parsed.get("issuer", ""),
                            "submission_rules": parsed.get("submission_rules", []),
                            "wps_formula": parsed.get("wps_formula", "")}),
                json.dumps(gates),
                json.dumps(criterion_results),
                json.dumps(selected.get("gate_results", [])),
                json.dumps(
                    {
                        **selected.get("scenarios", {}).get(scenario, {}),
                        "verdict": selected.get("verdict"),
                        "binding_constraint": selected.get("binding_constraint", ""),
                        "explanation": _build_wps_explanation(
                            scenario, selected, criterion_results, poison_pills
                        ),
                    }
                ),
                json.dumps(wps_results),
                json.dumps(poison_pills),
            ),
        )
        analysis_id = cur.lastrowid
        db.execute("UPDATE analysis_jobs SET status='complete', updated_at=datetime('now') WHERE job_id=?", (job.job_id,))
        db.commit()
        db.close()

        job.status = "complete"
        job.analysis_id = analysis_id
        emit({"event": "complete", "job_id": job.job_id, "analysis_id": analysis_id, "pct": 100})

    except Exception as e:
        job.status = "error"
        job.error = str(e)
        try:
            db = get_db()
            db.execute("UPDATE analysis_jobs SET status='error', error_message=?, updated_at=datetime('now') WHERE job_id=?",
                       (str(e)[:500], job.job_id))
            db.commit()
            db.close()
        except Exception:
            pass
        # Format API errors to be human-readable
        msg = str(e)
        if hasattr(e, 'status_code'):
            code = getattr(e, 'status_code', '')
            body = getattr(e, 'body', None) or getattr(e, 'message', msg)
            msg = f"API error {code}: {body}"
        emit({"event": "error", "message": msg})
    finally:
        # Must use call_soon_threadsafe so None is scheduled AFTER the error event above
        loop.call_soon_threadsafe(job.queue.put_nowait, None)


@router.post("/start")
async def start_analysis(body: StartIn, user: dict = Depends(get_current_user)):
    db = get_db()
    p = row(db.execute("SELECT * FROM projects WHERE id=?", (body.project_id,)).fetchone())
    db.close()
    if not p:
        raise HTTPException(404, "Project not found")
    if not p.get("rfp_filename"):
        raise HTTPException(400, "Project has no RFP PDF")

    rfp_path = str(UPLOAD_DIR / "rfp" / f"{body.project_id}_rfp.pdf")
    response_path = str(UPLOAD_DIR / "response" / f"{body.project_id}_response.pdf")

    job_id = str(uuid.uuid4())
    job = Job(job_id=job_id, project_id=body.project_id)
    _jobs[job_id] = job

    db = get_db()
    db.execute("INSERT INTO analysis_jobs (job_id, project_id, financial_scenario) VALUES (?,?,?)",
               (job_id, body.project_id, body.financial_scenario))
    db.commit()
    db.close()

    _safety.record_event(
        route="analysis",
        context="analysis_start",
        event_type="confidentiality_notice_enforced",
        action_taken="warn_allow",
        user_id=user["id"],
        metadata={"project_id": body.project_id, "scenario": body.financial_scenario},
    )
    _safety.record_event(
        route="analysis",
        context="analysis_start",
        event_type="external_llm_processing",
        action_taken="analysis_sent_confidential_material",
        user_id=user["id"],
        metadata={"project_id": body.project_id, "scenario": body.financial_scenario},
    )

    asyncio.create_task(_run_pipeline(
        job, rfp_path,
        response_path if Path(response_path).exists() else None,
        body.financial_scenario,
    ))
    return {"job_id": job_id, "status": "queued"}


@router.get("/stream/{job_id}")
async def stream(job_id: str, token: str = Query(...)):
    get_current_user_from_token(token)
    job = _jobs.get(job_id)

    if job:
        async def generate_live():
            while True:
                event = await job.queue.get()
                if event is None:
                    break
                yield f"data: {json.dumps(event)}\n\n"
        return StreamingResponse(generate_live(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # Job not in memory — fall back to DB for completed/errored jobs
    db = get_db()
    db_job = row(db.execute(
        "SELECT aj.status, aj.error_message, ar.id as result_id "
        "FROM analysis_jobs aj LEFT JOIN analysis_results ar ON ar.job_id=aj.job_id "
        "WHERE aj.job_id=?", (job_id,)
    ).fetchone())
    db.close()

    if not db_job:
        raise HTTPException(404, "Job not found")

    if db_job["status"] == "complete":
        event = json.dumps({"event": "complete", "job_id": job_id, "analysis_id": db_job["result_id"], "pct": 100})
    else:
        msg = db_job.get("error_message") or "Job did not complete"
        event = json.dumps({"event": "error", "message": msg})

    async def generate_synthetic():
        yield f"data: {event}\n\n"

    return StreamingResponse(generate_synthetic(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/active/{project_id}")
def get_active_job(project_id: int, user: dict = Depends(get_current_user)):
    for job_id, job in _jobs.items():
        if job.project_id == project_id and job.status in ("queued", "running"):
            return {"job_id": job_id, "status": job.status}
    db = get_db()
    r = row(db.execute(
        "SELECT aj.job_id, aj.status, ar.id as result_id FROM analysis_jobs aj "
        "LEFT JOIN analysis_results ar ON ar.job_id=aj.job_id "
        "WHERE aj.project_id=? ORDER BY aj.created_at DESC LIMIT 1",
        (project_id,),
    ).fetchone())
    db.close()
    return r or {"job_id": None, "status": None}


@router.get("/project/{pid}")
def list_analyses(pid: int, user: dict = Depends(get_current_user)):
    db = get_db()
    js = rows(db.execute(
        "SELECT aj.*, ar.id as result_id FROM analysis_jobs aj LEFT JOIN analysis_results ar ON ar.job_id=aj.job_id WHERE aj.project_id=? ORDER BY aj.created_at DESC",
        (pid,),
    ).fetchall())
    db.close()
    return js


@router.get("/result/{aid}")
def get_result(aid: int, user: dict = Depends(get_current_user)):
    db = get_db()
    r = row(db.execute("SELECT * FROM analysis_results WHERE id=?", (aid,)).fetchone())
    db.close()
    if not r:
        raise HTTPException(404, "Result not found")
    for col in ("rfp_meta_json", "gates_json", "criterion_results_json",
                "gate_results_json", "wps_summary_json", "scenarios_json", "poison_pills_json"):
        try:
            r[col.replace("_json", "")] = json.loads(r.pop(col) or "null")
        except Exception:
            r[col.replace("_json", "")] = None
    return r
