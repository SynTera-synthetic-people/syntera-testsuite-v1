"""Report Routes"""
from fastapi import APIRouter, HTTPException, Depends, Query, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from database.connection import get_db
from backend.models.survey import Survey
from backend.utils.json_helpers import sanitize_for_json
from datetime import datetime
import json

router = APIRouter()

# Matches ml_engine/comparison_engine.py — documented for report readers.
STATISTICAL_TESTS_REFERENCE: list[dict[str, str]] = [
    {
        "test": "chi_square",
        "display": "Chi-square",
        "purpose": "Whether synthetic and real values fall into the same histogram bins (frequency pattern).",
        "key_metric": "p-value / match score — higher suggests similar binned counts.",
    },
    {
        "test": "ks_test",
        "display": "Kolmogorov–Smirnov",
        "purpose": "Whether the two samples follow the same overall distribution (empirical CDF).",
        "key_metric": "KS statistic and p-value — smaller D or higher p-value suggests closer distributions.",
    },
    {
        "test": "jensen_shannon",
        "display": "Jensen–Shannon",
        "purpose": "Similarity of the two vectors treated as probability masses (symmetric distance).",
        "key_metric": "Divergence — lower is closer; match score is derived from 1 − divergence.",
    },
    {
        "test": "mann_whitney",
        "display": "Mann–Whitney U",
        "purpose": "Non-parametric comparison of ranks / typical level between the two groups.",
        "key_metric": "p-value / match score — higher p-value suggests more similar location.",
    },
    {
        "test": "t_test",
        "display": "Independent t-test",
        "purpose": "Whether the two groups have the same mean (parametric).",
        "key_metric": "p-value / match score — higher p-value suggests similar means.",
    },
    {
        "test": "anderson_darling",
        "display": "Anderson–Darling k-sample",
        "purpose": "Whether both samples come from the same distribution (sensitive to tails).",
        "key_metric": "p-value or normalized statistic — higher p-value / lower statistic suggests same distribution.",
    },
    {
        "test": "wasserstein_distance",
        "display": "Wasserstein (earth mover)",
        "purpose": "Minimum “transport cost” to reshape one empirical distribution into the other.",
        "key_metric": "Distance and normalized distance — lower distance means closer distributions.",
    },
    {
        "test": "correlation",
        "display": "Pearson & Spearman",
        "purpose": "After trimming to equal length, linear and monotonic alignment point-by-point.",
        "key_metric": "Pearson r, Spearman r, average correlation — meaningful only when indices are paired.",
    },
    {
        "test": "error_metrics",
        "display": "MAE & RMSE",
        "purpose": "Mean absolute error and RMSE between aligned synthetic and real series.",
        "key_metric": "MAE / RMSE (and normalized) — lower error means closer paired values.",
    },
    {
        "test": "distribution_summary",
        "display": "Summary statistics",
        "purpose": "How close means, standard deviations, and medians are between the two samples.",
        "key_metric": "Normalized mean/std gaps — smaller gaps mean closer summary statistics.",
    },
    {
        "test": "kullback_leibler",
        "display": "Kullback–Leibler",
        "purpose": "Information-theoretic gap between normalized distributions.",
        "key_metric": "KL divergence (normalized) — lower divergence means closer distributions.",
    },
    {
        "test": "cramer_von_mises",
        "display": "Cramér–von Mises",
        "purpose": "Two-sample test that both samples share the same underlying distribution.",
        "key_metric": "p-value / statistic — higher p-value or lower statistic suggests same distribution.",
    },
]


def _statistical_tests_guide_html() -> str:
    rows = []
    for row in STATISTICAL_TESTS_REFERENCE:
        tid = row["test"]
        disp = row["display"]
        rows.append(
            f"<tr><td><strong>{disp}</strong><br><span class=\"test-id\">({tid})</span></td>"
            f"<td>{row['purpose']}</td><td>{row['key_metric']}</td></tr>"
        )
    return f"""
            <div class="stat-tests-guide-section">
                <h2 class="section-title">What each statistical test measures</h2>
                <p class="stat-tests-guide-intro">Twelve complementary checks compare synthetic vs real numeric responses. Match each row to the same test name in the results below.</p>
                <div class="stat-tests-table-wrap">
                    <table class="stat-tests-table">
                        <thead>
                            <tr><th>Test</th><th>What it assesses</th><th>Key metric to read</th></tr>
                        </thead>
                        <tbody>{"".join(rows)}</tbody>
                    </table>
                </div>
            </div>
    """


@router.get("/{survey_id}")
async def get_report(survey_id: str, db: Session = Depends(get_db)):
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    avg_s = survey.avg_similarity if survey.avg_similarity is not None else survey.accuracy_score
    return {
        "survey_id": survey_id,
        "title": survey.title,
        "accuracy": survey.accuracy_score,
        "avg_similarity": avg_s,
        "actions_data_points": survey.actions_data_points,
        "neuroscience_data_points": survey.neuroscience_data_points,
        "contextual_layer_data_points": survey.contextual_layer_data_points,
        "directional_alignment": survey.directional_alignment,
        "checks_passed": survey.checks_passed,
        "study_metrics": sanitize_for_json(
            {
                "actions_data_points": survey.actions_data_points,
                "neuroscience_data_points": survey.neuroscience_data_points,
                "contextual_layer_data_points": survey.contextual_layer_data_points,
                "avg_similarity": avg_s,
                "directional_alignment": survey.directional_alignment,
                "avg_prediction_accuracy": getattr(survey, "avg_prediction_accuracy", None),
                "avg_relationship_strength": getattr(survey, "avg_relationship_strength", None),
                "checks_passed": survey.checks_passed,
            }
        ),
        "created_at": survey.created_at,
    }


@router.get("/{survey_id}/download", response_class=HTMLResponse)
async def download_report(survey_id: str, format: str = "html", db: Session = Depends(get_db)):
    """Generate a downloadable formatted report for client presentation."""
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")

    if not survey.test_suite_report:
        raise HTTPException(
            status_code=404, detail="No validation results found. Run validation first."
        )

    if format == "json":
        # Return JSON format
        avg_s = survey.avg_similarity if survey.avg_similarity is not None else survey.accuracy_score
        study_metrics = {
            "actions_data_points": survey.actions_data_points,
            "neuroscience_data_points": survey.neuroscience_data_points,
            "contextual_layer_data_points": survey.contextual_layer_data_points,
            "avg_similarity": avg_s,
            "directional_alignment": survey.directional_alignment,
            "avg_prediction_accuracy": getattr(survey, "avg_prediction_accuracy", None),
            "avg_relationship_strength": getattr(survey, "avg_relationship_strength", None),
            "checks_passed": survey.checks_passed,
        }
        report_data = {
            "survey": {
                "id": survey.id,
                "title": survey.title,
                "description": survey.description,
                "created_at": survey.created_at.isoformat() if survey.created_at else None,
                "validated_at": survey.validated_at.isoformat() if survey.validated_at else None,
                "accuracy_score": survey.accuracy_score,
                "avg_similarity": avg_s,
                "actions_data_points": survey.actions_data_points,
                "neuroscience_data_points": survey.neuroscience_data_points,
                "contextual_layer_data_points": survey.contextual_layer_data_points,
                "directional_alignment": survey.directional_alignment,
                "avg_prediction_accuracy": getattr(survey, "avg_prediction_accuracy", None),
                "avg_relationship_strength": getattr(survey, "avg_relationship_strength", None),
                "checks_passed": survey.checks_passed,
            },
            "study_metrics": sanitize_for_json(study_metrics),
            "results": {
                "overall_accuracy": survey.accuracy_score,
                "validation_status": survey.validation_status,
            },
            "test_suite": survey.test_suite_report,
            "statistical_tests_reference": STATISTICAL_TESTS_REFERENCE,
        }
        return Response(
            content=json.dumps(report_data, indent=2, default=str),
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="syntera_report_{survey_id}.json"'
            },
        )

    # Generate HTML report
    # Ensure report is a dict
    if not isinstance(survey.test_suite_report, dict):
        raise HTTPException(
            status_code=400, detail="Invalid report format. Please run validation again."
        )
    
    report = survey.test_suite_report
    accuracy = float(survey.accuracy_score or 0.0)
    sm_embed = report.get("study_metrics") if isinstance(report, dict) else {}
    ap = survey.actions_data_points if survey.actions_data_points is not None else sm_embed.get("actions_data_points")
    np_ = survey.neuroscience_data_points if survey.neuroscience_data_points is not None else sm_embed.get("neuroscience_data_points")
    cp = survey.contextual_layer_data_points if survey.contextual_layer_data_points is not None else sm_embed.get("contextual_layer_data_points")
    da = survey.directional_alignment if survey.directional_alignment is not None else sm_embed.get("directional_alignment")
    chk = survey.checks_passed if survey.checks_passed is not None else sm_embed.get("checks_passed")
    apred = getattr(survey, "avg_prediction_accuracy", None)
    if apred is None:
        apred = sm_embed.get("avg_prediction_accuracy")
    arel = getattr(survey, "avg_relationship_strength", None)
    if arel is None:
        arel = sm_embed.get("avg_relationship_strength")

    def _fmt_study_val(v) -> str:
        if v is None:
            return "N/A"
        return str(v)

    def _fmt_align_pct(v) -> str:
        if v is None:
            return "N/A"
        try:
            x = float(v)
            return f"{x * 100:.1f}%" if x <= 1.0 else f"{x:.1f}%"
        except (TypeError, ValueError):
            return str(v)

    study_metrics_rows = f"""
            <div class="study-metrics-section">
                <h2 class="section-title">Survey study metrics</h2>
                <div class="study-metrics-grid">
                    <div class="study-metric-card"><h3>Action data points</h3><div class="value">{_fmt_study_val(ap)}</div></div>
                    <div class="study-metric-card"><h3>Neuroscience signals</h3><div class="value">{_fmt_study_val(np_)}</div></div>
                    <div class="study-metric-card"><h3>Contextual layer points</h3><div class="value">{_fmt_study_val(cp)}</div></div>
                    <div class="study-metric-card"><h3>Avg similarity</h3><div class="value">{accuracy:.1%}</div></div>
                    <div class="study-metric-card"><h3>Directional alignment</h3><div class="value">{_fmt_align_pct(da)}</div></div>
                    <div class="study-metric-card"><h3>Avg prediction accuracy</h3><div class="value">{_fmt_align_pct(apred)}</div></div>
                    <div class="study-metric-card"><h3>Avg relationship strength</h3><div class="value">{_fmt_align_pct(arel)}</div></div>
                    <div class="study-metric-card"><h3>Checks passed</h3><div class="value">{_fmt_study_val(chk)}</div></div>
                </div>
            </div>
    """

    def _accent_from_accuracy(acc: float) -> str:
        p = acc * 100
        if p >= 85:
            return "#10b981"
        if p >= 75:
            return "#f59e0b"
        if p >= 50:
            return "#ef4444"
        return "#7c3aed"

    accent = _accent_from_accuracy(accuracy)

    # Format test results
    test_results_html = ""
    tests = report.get("tests", [])
    if not isinstance(tests, list):
        tests = []
    
    for test in tests:
        if "error" in test:
            test_results_html += f"""
            <div class="test-result error">
                <h4>{test.get('test', 'Unknown')}</h4>
                <p class="error-msg">Error: {test['error']}</p>
            </div>
            """
        else:
            test_name = test.get("test", "Unknown Test")
            ms = test.get("match_score")
            try:
                test_accent = _accent_from_accuracy(float(ms)) if ms is not None else accent
            except (TypeError, ValueError):
                test_accent = accent

            test_results_html += f"""
            <div class="test-result" style="border-left-color: {test_accent};">
                <div class="test-header">
                    <h4>{test_name.replace('_', ' ').title()}</h4>
                </div>
                <div class="test-metrics">
            """

            # Add all test metrics
            for key, value in test.items():
                if key not in ["test", "tier"]:
                    if isinstance(value, float):
                        formatted_value = f"{value:.4f}"
                    else:
                        formatted_value = str(value)
                    test_results_html += f"""
                    <div class="metric">
                        <span class="metric-label">{key.replace('_', ' ').title()}:</span>
                        <span class="metric-value">{formatted_value}</span>
                    </div>
                    """

            test_results_html += """
                </div>
            </div>
            """

    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SynTera Test Suite Report - {survey.title}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #1f2937;
            background: #f9fafb;
            padding: 40px 20px;
        }}
        .report-container {{
            max-width: 900px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .report-header {{
            background: linear-gradient(135deg, #404685 0%, #00D4EC 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        .report-header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        .report-header p {{
            font-size: 1.1em;
            opacity: 0.9;
        }}
        .report-body {{
            padding: 40px;
        }}
        .summary-section {{
            background: #f9fafb;
            border-radius: 8px;
            padding: 30px;
            margin-bottom: 40px;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        .summary-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid {accent};
        }}
        .summary-card h3 {{
            font-size: 0.9em;
            text-transform: uppercase;
            color: #6b7280;
            margin-bottom: 10px;
        }}
        .summary-card .value {{
            font-size: 2em;
            font-weight: bold;
            color: {accent};
        }}
        .tier-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            color: white;
            font-size: 0.85em;
            font-weight: 600;
            text-transform: uppercase;
        }}
        .section-title {{
            font-size: 1.5em;
            margin-bottom: 20px;
            color: #1f2937;
            border-bottom: 2px solid #e5e7eb;
            padding-bottom: 10px;
        }}
        .test-result {{
            background: #f9fafb;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            border-left: 4px solid {accent};
        }}
        .test-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }}
        .test-header h4 {{
            font-size: 1.2em;
            color: #1f2937;
        }}
        .test-metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }}
        .metric {{
            display: flex;
            flex-direction: column;
        }}
        .metric-label {{
            font-size: 0.85em;
            color: #6b7280;
            margin-bottom: 5px;
        }}
        .metric-value {{
            font-size: 1.1em;
            font-weight: 600;
            color: #1f2937;
        }}
        .error {{
            border-left-color: #ef4444;
        }}
        .error-msg {{
            color: #ef4444;
            font-weight: 500;
        }}
        .metadata {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e5e7eb;
            color: #6b7280;
            font-size: 0.9em;
        }}
        .metadata p {{
            margin: 5px 0;
        }}
        .study-metrics-section {{
            margin-bottom: 32px;
        }}
        .study-metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-top: 16px;
        }}
        .study-metric-card {{
            background: #f9fafb;
            border-radius: 8px;
            padding: 16px;
            border-left: 4px solid #00D4EC;
        }}
        .study-metric-card h3 {{
            font-size: 0.85em;
            text-transform: uppercase;
            color: #6b7280;
            margin-bottom: 8px;
        }}
        .study-metric-card .value {{
            font-size: 1.35em;
            font-weight: 700;
            color: #1f2937;
        }}
        .stat-tests-guide-section {{
            margin-bottom: 32px;
        }}
        .stat-tests-guide-intro {{
            color: #4b5563;
            font-size: 0.95em;
            line-height: 1.55;
            margin-bottom: 16px;
        }}
        .stat-tests-table-wrap {{
            overflow-x: auto;
        }}
        .stat-tests-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.88em;
            min-width: 620px;
        }}
        .stat-tests-table th,
        .stat-tests-table td {{
            border: 1px solid #e5e7eb;
            padding: 10px 12px;
            text-align: left;
            vertical-align: top;
        }}
        .stat-tests-table th {{
            background: #f3f4f6;
            font-weight: 600;
            color: #1f2937;
        }}
        .stat-tests-table tbody tr:nth-child(even) {{
            background: #fafafa;
        }}
        .test-id {{
            font-size: 0.85em;
            color: #6b7280;
            font-weight: 400;
        }}
        @media print {{
            body {{ background: white; padding: 0; }}
            .report-container {{ box-shadow: none; }}
        }}
    </style>
</head>
<body>
    <div class="report-container">
        <div class="report-header">
            <h1>SynTera Test Suite Report</h1>
            <p>Statistical Validation Analysis</p>
        </div>
        <div class="report-body">
            <div class="summary-section">
                <h2 style="margin-bottom: 10px;">Survey: {survey.title}</h2>
                {f'<p style="color: #6b7280; margin-bottom: 20px;">{survey.description}</p>' if survey.description else ''}
                <div class="summary-grid">
                    <div class="summary-card">
                        <h3>Overall Accuracy</h3>
                        <div class="value">{accuracy:.1%}</div>
                    </div>
                    <div class="summary-card">
                        <h3>Test Status</h3>
                        <div class="value" style="font-size: 1.2em; color: {accent};">{survey.validation_status}</div>
                    </div>
                </div>
            </div>

            {study_metrics_rows}

            {_statistical_tests_guide_html()}

            <h2 class="section-title">Test Suite Results</h2>
            <div class="test-results">
                {test_results_html}
            </div>

            <div class="metadata">
                <p><strong>Survey ID:</strong> {survey.id}</p>
                <p><strong>Created:</strong> {survey.created_at.strftime('%Y-%m-%d %H:%M:%S UTC') if survey.created_at else 'N/A'}</p>
                <p><strong>Validated:</strong> {survey.validated_at.strftime('%Y-%m-%d %H:%M:%S UTC') if survey.validated_at else 'N/A'}</p>
                <p><strong>Data Sizes:</strong> Synthetic: {report.get('synthetic_size', 0)} | Real: {report.get('real_size', 0)}</p>
                <p style="margin-top: 20px; font-size: 0.85em;">
                    Generated by SynTera Test Suite on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
                </p>
            </div>
        </div>
    </div>
</body>
</html>
    """

    return Response(
        content=html_content,
        media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="syntera_report_{survey_id}.html"'},
    )

