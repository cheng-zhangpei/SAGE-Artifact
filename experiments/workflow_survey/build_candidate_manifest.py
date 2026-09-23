"""Freeze the source review of the detector-defined workflow population.

The structural detector is intentionally broad.  This file records every one of
its candidates, including invalid and unresolved cases, so downstream SAGE runs
cannot silently retain only positive examples.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


CONFIRMED = "confirmed_collision_under_reviewed_contract"
NO_COLLISION = "no_collision_provenance_already_observed"
INVALID = "invalid_structural_candidate"
UNRESOLVED = "contract_unresolved"


# Human review decisions.  Labels and destination policies remain study inputs;
# "confirmed" therefore means that the checked workflow dependency can realize
# a formal SAGE collision under the stated paired policy fixture.  It does not
# mean that a production incident was observed.
REVIEWS = {
    6531: (CONFIRMED, "transform", ["Image Style"], "Save Image",
           "A Drive reference image enters image generation without entering the earlier creator-agent context; the rendered image retains its provenance."),
    7201: (NO_COLLISION, "derived", ["Google Drive-get_file"], "Gmail",
           "The downloaded offer is the stored form of the preceding LLM output; no independently protected input is introduced."),
    7369: (INVALID, None, [], None,
           "The HTTP file output field is dynamic and does not match the upload node's literal input field, so the binary dependency is not established."),
    7695: (NO_COLLISION, "derived", ["Download file"], "Send Email",
           "The downloaded slides are generated from data already supplied to the agent; the download does not introduce an independent provenance."),
    8104: (CONFIRMED, "direct_resource", ["Google Drive"], "Gmail",
           "A fixed proposal template is copied, filled, exported, and attached; the earlier AI reads the transcript rather than the template resource."),
    9146: (NO_COLLISION, "derived", ["Download PDF from URL"], "Save PDF to Drive",
           "The downloaded PDF is generated solely from the meeting summary/action-item outputs and public formatting, all already represented upstream."),
    10126: (CONFIRMED, "transform", ["Generate Thumbnail via Templated.io"], "Upload to Google Drive",
            "A fixed remote template is combined with AI text and the rendered thumbnail is uploaded; the template resource is absent from the earlier AI context."),
    10441: (NO_COLLISION, "derived", ["Generate PDF"], "Send Email",
            "The PDF is a rendering of the AI report HTML and introduces no independently protected field or resource."),
    10880: (NO_COLLISION, "derived", ["PDF creator"], "Send PDF",
            "The PDF contains generated moodboard output and public rendering assets; no independently protected input is established by the workflow."),
    11529: (CONFIRMED, "direct_resource", ["Get Email Attachments"], "Save Photos to Drive",
            "Attachment bytes are fetched after the extractor reads email text; the photo resource is not part of the extractor's context."),
    11730: (INVALID, None, [], None,
            "Candidate edges include a nonexistent PDF-to-follow-up path and attachment arrays without a named binary property."),
    11745: (CONFIRMED, "context_projection", ["Generate Review Card HTML"], "Send Review to Employee",
            "The rendered review includes managerName, reviewId, and reviewDate merged after AI summarization; those fields are absent from the AI prompt."),
    11912: (NO_COLLISION, "already_observed", ["Get a message1"], "Upload file1",
            "A downstream AI explicitly reads text extracted from the same attachment before upload."),
    12731: (CONFIRMED, "context_projection", ["Generate Feedback HTML"], "Send Student Feedback Email",
            "The feedback PDF includes student identity and workflow fields omitted from the grading-agent prompts."),
    12959: (NO_COLLISION, "derived", ["Convert Doc to PDF"], "Send Proposal via Email",
            "The proposal document is created from the normalized client data and preceding AI proposal output; no external template is copied."),
    13237: (NO_COLLISION, "already_observed", ["Get Attachment"], "Forward to freee",
            "The classifier reads extracted content from the same message attachment before it is refetched and forwarded."),
    13408: (UNRESOLVED, None, [], None,
            "The CV identifier is an empty deployment placeholder and the historical attachmentsBinary boolean contract cannot be confirmed from the artifact."),
    13659: (NO_COLLISION, "derived", ["Download PDF"], "Send Report Email",
            "Charts are deterministic renderings of analyzed metrics and the embedded logo/template is a workflow constant; no protected independent runtime input is established."),
    14185: (CONFIRMED, "direct_resource", ["Copy Template"], "Send Quotation Email",
            "A fixed Google Docs quotation template is copied and exported after personalization; the AI does not read the template resource."),
    14717: (CONFIRMED, "direct_resource", ["Copy Proposal Template"], "Send Proposal Email",
            "A fixed Docs template is copied, filled, exported, downloaded, and attached; its resource provenance is absent from the proposal AI context."),
    15440: (NO_COLLISION, "already_observed", ["18. HTTP — Download Clip File"], "19. Google Drive — Upload Clip",
            "The caption agent receives the video summary and timestamps from the same source-video/clip lineage; the conservative union-flow model already carries that provenance."),
    15449: (CONFIRMED, "direct_resource", ["Download Handbook", "Download Policy"], "Welcome Email → New Hire",
            "Handbook and policy files are downloaded after the AI reads form fields, then attached to the welcome email."),
    15451: (CONFIRMED, "direct_resource", ["Download Handbook", "Download Policy"], "Welcome Email → New Hire",
            "Same independently downloaded handbook/policy structure as 15449; retained as a duplicate template, not a distinct application."),
    16217: (CONFIRMED, "context_projection", ["Build HTML Report"], "Send a message",
            "The PDF contains post thumbnails, full captions, and permalinks while the AI prompt contains only truncated top-post text and aggregate metrics."),
    16375: (NO_COLLISION, "derived", ["Resume PDF (DocRaptor)", "Cover PDF (DocRaptor)"], "Email Me (Gmail)",
            "Both PDFs render the resume/cover outputs of the preceding agents plus public templates; no independent protected resource is introduced."),
    16538: (INVALID, None, [], None,
            "Outlook expects binary field report_pdf, but the export node does not establish that field."),
    16551: (INVALID, None, [], None,
            "Named expressions reference an absent node and the email attachment has no named binary property."),
    16876: (INVALID, None, [], None,
            "The email attachment array is empty, so the PDF-to-sink binary dependency is not established."),
    16881: (NO_COLLISION, "derived", ["Generate Sound With ElevenLabs"], "Upload to Google Drive",
            "The audio is generated from the AI-produced sound prompt; new bytes alone do not constitute independent protected provenance."),
    17351: (NO_COLLISION, "derived", ["Fetch Tech Score Chart"], "Send Email via Gmail",
            "The chart is a deterministic rendering of the score already represented in the report data."),
    17933: (NO_COLLISION, "already_observed", ["Render PDF (Gotenberg)"], "Email the pack",
            "The teaching-pack agent reads the source paper text and the PDF is a rendering of its output."),
    18053: (CONFIRMED, "context_projection", ["Build HTML Report"], "Send Email",
            "The PDF embeds ad thumbnail URLs and detailed creative fields; the AI prompt supplies only selected creative metrics and omits thumbnails."),
    18142: (NO_COLLISION, "already_observed", ["Fetch Actual Image"], "Download Image",
            "The selector analyzes the candidate image URLs before the selected variant is fetched and uploaded; the conservative resource-identity contract preserves provenance."),
    18341: (NO_COLLISION, "already_observed", ["Download the clip"], "Save the clip to Drive",
            "The clip remains a derivative of the uploaded source video and its processing lineage is already observed."),
    18417: (NO_COLLISION, "already_observed", ["Download file"], "Upload File to Google Drive",
            "The image input is read by the image-analysis agent; later image variants retain that source provenance."),
    18477: (INVALID, None, [], None,
            "Expressions reference a nonexistent Process & Flag Students1 node, preventing a valid executable dependency path."),
    18673: (CONFIRMED, "context_projection", ["Format Email Template (HTML)"], "Email CFO Report (Gmail)",
            "The report adds an internal dashboard URL after AI summarization; that URL is absent from the AI prompt and flows into the emailed PDF."),
    19292: (CONFIRMED, "direct_resource", ["Download Attachment from Drive"], "Create Draft with Attachment",
            "A separately configured Drive file is downloaded only after Gemini builds the recipient/body and is attached to the draft."),
}


def build(summary: dict) -> dict:
    rows = summary["structural_candidates"]
    ids = {int(row["id"]) for row in rows}
    if ids != set(REVIEWS):
        raise ValueError(f"review coverage mismatch: missing={sorted(ids-set(REVIEWS))}, extra={sorted(set(REVIEWS)-ids)}")
    candidates = []
    for row in sorted(rows, key=lambda x: int(x["id"])):
        wid = int(row["id"])
        status, subtype, sources, sink, evidence = REVIEWS[wid]
        record = {
            "id": wid,
            "name": row["name"],
            "author": row.get("author"),
            "source_sha256": row["source_sha256"],
            "structure_fingerprint": row["structure_fingerprint"],
            "detected_paths": row["late_file_paths"],
            "final_status": status,
            "subtype": subtype,
            "review_evidence": evidence,
            "policy_scope": "paired study fixture; labels and destination policy supplied by the study",
            "runtime_claim": "source dependency review, not a measured production incident",
        }
        if status in (CONFIRMED, NO_COLLISION):
            required = list(dict.fromkeys([*row.get("main_ai_nodes", []), *sources, sink]))
            record["sage_model"] = {
                "kind": "independent_binary" if status == CONFIRMED else "generated_from_ctx",
                "sources": sources,
                "sink": sink,
                "required_nodes": required,
            }
        candidates.append(record)
    counts = Counter(c["final_status"] for c in candidates)
    positive_fps = {c["structure_fingerprint"] for c in candidates if c["final_status"] == CONFIRMED}
    return {
        "schema_version": 1,
        "population": "all 38 workflows returned by the frozen narrow late-resource detector",
        "claim": "collision susceptibility under source-reviewed contracts and explicit paired policy fixtures",
        "non_claim": "not ecosystem prevalence and not observed production false-positive rate",
        "counts": dict(sorted(counts.items())),
        "confirmed_distinct_structure_fingerprints": len(positive_fps),
        "candidates": candidates,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = build(json.loads(args.summary.read_text(encoding="utf-8")))
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"counts": manifest["counts"], "distinct_positive_structures": manifest["confirmed_distinct_structure_fingerprints"]}))


if __name__ == "__main__":
    main()
