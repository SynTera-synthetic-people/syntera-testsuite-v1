"""Report Routes"""
from fastapi import APIRouter, HTTPException, Depends, Query, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from database.connection import get_db
from backend.models.survey import Survey
from datetime import datetime
import json

router = APIRouter()


@router.get("/{survey_id}")
async def get_report(survey_id: str, db: Session = Depends(get_db)):
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    return {
        "survey_id": survey_id,
        "title": survey.title,
        "accuracy": survey.accuracy_score,
        "tier": survey.confidence_tier,
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
        report_data = {
            "survey": {
                "id": survey.id,
                "title": survey.title,
                "description": survey.description,
                "created_at": survey.created_at.isoformat() if survey.created_at else None,
                "validated_at": survey.validated_at.isoformat() if survey.validated_at else None,
            },
            "results": {
                "overall_accuracy": survey.accuracy_score,
                "confidence_tier": survey.confidence_tier,
                "validation_status": survey.validation_status,
            },
            "test_suite": survey.test_suite_report,
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
    tier = survey.confidence_tier or "N/A"
    accuracy = survey.accuracy_score or 0.0

    # Format tier badge color
    tier_colors = {
        "TIER_1": "#10b981",  # green
        "TIER_2": "#f59e0b",  # amber
        "TIER_3": "#ef4444",  # red
    }
    tier_color = tier_colors.get(tier, "#6b7280")

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
            test_tier = test.get("tier", "N/A")
            test_tier_color = tier_colors.get(test_tier, "#6b7280")

            test_results_html += f"""
            <div class="test-result">
                <div class="test-header">
                    <h4>{test_name.replace('_', ' ').title()}</h4>
                    <span class="tier-badge" style="background: {tier_colors.get(test_tier, '#6b7280')}">{test_tier}</span>
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
            border-left: 4px solid {tier_color};
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
            color: {tier_color};
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
            border-left: 4px solid {tier_color};
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
                        <h3>Confidence Tier</h3>
                        <div class="value" style="font-size: 1.5em;">
                            <span class="tier-badge" style="background: {tier_color}">{tier}</span>
                        </div>
                    </div>
                    <div class="summary-card">
                        <h3>Test Status</h3>
                        <div class="value" style="font-size: 1.2em; color: {tier_color};">{survey.validation_status}</div>
                    </div>
                </div>
            </div>

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

