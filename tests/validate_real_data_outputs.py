from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
WEB_DATA_DIR = PROJECT_ROOT / "web" / "data"


REQUIRED_RAW = [
    "github_work_items.json",
    "repository_metadata.json",
]

REQUIRED_OUTPUTS = [
    "work_item_risk_predictions.csv",
    "program_health_summary.csv",
    "risk_action_queue.csv",
    "dependency_blocker_view.csv",
    "portfolio_flow_timeline.csv",
    "executive_status_briefs.csv",
    "executive_kpis.csv",
    "model_metrics.csv",
    "feature_importance.csv",
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def read_csv(name: str) -> pd.DataFrame:
    path = OUTPUT_DIR / name
    require(path.exists(), f"Missing Required Output: {path}")
    return pd.read_csv(path)


def main() -> None:
    missing_raw = [name for name in REQUIRED_RAW if not (RAW_DIR / name).exists()]
    require(not missing_raw, f"Missing Raw GitHub Data Files: {missing_raw}")

    missing_outputs = [name for name in REQUIRED_OUTPUTS if not (OUTPUT_DIR / name).exists()]
    require(not missing_outputs, f"Missing Output Files: {missing_outputs}")

    executive = read_csv("executive_kpis.csv")
    require(len(executive) == 1, "Executive KPIs Should Have One Row")
    kpis = executive.iloc[0]
    require(kpis["project_owner"] == "Project Demo", "Project Owner Must Be Project Demo")
    require("GitHub" in kpis["data_source"], "Data Source Must Reference Real GitHub Data")
    require(int(kpis["programs_analyzed"]) >= 5, "At Least Five Programs Should Be Analyzed")
    require(int(kpis["work_items_scored"]) >= 1000, "A Meaningful Real Work Item Set Is Required")
    require(float(kpis["model_roc_auc"]) >= 0.6, "Model ROC AUC Is Below Validation Floor")

    work_items = read_csv("work_item_risk_predictions.csv")
    required_columns = {
        "program",
        "source_repo",
        "item_type",
        "item_url",
        "delay_risk_probability",
        "delay_risk_score",
        "risk_level",
        "recommended_action",
    }
    require(required_columns.issubset(work_items.columns), "Work Item Risk Columns Missing")
    require(work_items["item_url"].str.contains("github.com", na=False).all(), "Work Items Must Link To GitHub")
    require(work_items["delay_risk_probability"].between(0, 1).all(), "Risk Probabilities Must Be 0-1")
    require(work_items["delay_risk_score"].between(0, 100).all(), "Risk Scores Must Be 0-100")

    program_health = read_csv("program_health_summary.csv")
    require(program_health["program_health_score"].between(0, 100).all(), "Program Health Scores Must Be 0-100")
    require({"Red", "Amber", "Green"}.intersection(set(program_health["program_status"])), "Program Status Values Missing")

    action_queue = read_csv("risk_action_queue.csv")
    require(len(action_queue) >= 20, "Action Queue Should Include Ranked PMO Actions")
    require(action_queue["recommended_action"].notna().all(), "Action Queue Recommendations Must Be Populated")

    dependency = read_csv("dependency_blocker_view.csv")
    require(len(dependency) >= 10, "Dependency View Should Include Real Signals")

    metrics = read_csv("model_metrics.csv")
    require({"ROC AUC", "Average Precision", "F1", "Accuracy"}.issubset(set(metrics["metric"])), "Model Metrics Are Incomplete")

    dashboard_json = WEB_DATA_DIR / "dashboard_data.json"
    dashboard_js = WEB_DATA_DIR / "dashboard_data.js"
    require(dashboard_json.exists(), "Dashboard JSON Missing")
    require(dashboard_js.exists(), "Dashboard JS Missing")
    payload = json.loads(dashboard_json.read_text(encoding="utf-8"))
    require(payload["generatedFor"] == "Project Demo", "Dashboard Payload Owner Is Incorrect")
    require(len(payload["programHealth"]) >= 5, "Dashboard Program Health Payload Is Missing")
    require(len(payload["actionQueue"]) >= 20, "Dashboard Action Queue Payload Is Too Small")
    require(len(payload["statusBriefs"]) >= 5, "Dashboard Status Briefs Missing")

    print("AI PMO Real-Data Output Validation Passed.")


if __name__ == "__main__":
    main()
