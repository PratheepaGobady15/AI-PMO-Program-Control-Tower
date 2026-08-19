from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import accuracy_score, average_precision_score, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
WEB_DATA_DIR = PROJECT_ROOT / "web" / "data"

RANDOM_SEED = 42
DELAY_THRESHOLD_DAYS = 14
STALE_UPDATE_DAYS = 3


@dataclass(frozen=True)
class ModelArtifacts:
    scored_items: pd.DataFrame
    metrics: pd.DataFrame
    feature_importance: pd.DataFrame


def require_files() -> None:
    missing = [
        path
        for path in [RAW_DIR / "github_work_items.json", RAW_DIR / "repository_metadata.json"]
        if not path.exists()
    ]
    if missing:
        missing_list = "\n".join(f"- {path}" for path in missing)
        raise FileNotFoundError(
            f"Missing Real GitHub Raw Data:\n{missing_list}\n\n"
            "Run `python src\\download_real_data.py` First."
        )


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def clean_label_text(labels: object) -> str:
    if not isinstance(labels, list):
        return ""
    names = []
    for label in labels:
        if isinstance(label, dict):
            names.append(str(label.get("name", "")))
    return " | ".join(name for name in names if name)


def flatten_work_items(raw_items: list[dict[str, object]], raw_metadata: list[dict[str, object]]) -> pd.DataFrame:
    repo_lookup = {}
    for metadata in raw_metadata:
        repo = str(metadata.get("full_name", ""))
        repo_lookup[repo] = {
            "repo_stars": metadata.get("stargazers_count", 0),
            "repo_forks": metadata.get("forks_count", 0),
            "repo_open_issues": metadata.get("open_issues_count", 0),
            "repo_watchers": metadata.get("watchers_count", 0),
            "repo_size": metadata.get("size", 0),
        }

    rows = []
    now = pd.Timestamp.now(tz="UTC")
    for item in raw_items:
        repo = str(item.get("_source_repo", ""))
        created_at = pd.to_datetime(item.get("created_at"), utc=True, errors="coerce")
        updated_at = pd.to_datetime(item.get("updated_at"), utc=True, errors="coerce")
        closed_at = pd.to_datetime(item.get("closed_at"), utc=True, errors="coerce")
        if pd.isna(created_at) or pd.isna(updated_at):
            continue

        labels = clean_label_text(item.get("labels"))
        assignees = item.get("assignees") if isinstance(item.get("assignees"), list) else []
        milestone = item.get("milestone") if isinstance(item.get("milestone"), dict) else None
        is_pr = isinstance(item.get("pull_request"), dict)
        state = str(item.get("state", "open"))
        end_date = closed_at if pd.notna(closed_at) else now
        age_days = max(float((now - created_at).total_seconds() / 86400), 0.0)
        cycle_time_days = max(float((end_date - created_at).total_seconds() / 86400), 0.0)
        time_since_update_days = max(float((now - updated_at).total_seconds() / 86400), 0.0)
        repo_meta = repo_lookup.get(repo, {})
        body = item.get("body") or ""
        title = item.get("title") or ""
        has_blocker_signal = int(bool(re.search(r"block|blocked|dependency|waiting|external|needs", labels, re.I)))
        has_bug_signal = int(bool(re.search(r"bug|regression|defect|failure|fix", labels, re.I)))
        has_priority_signal = int(bool(re.search(r"p0|p1|priority|critical|urgent|high", labels, re.I)))
        has_triage_signal = int(bool(re.search(r"triage|needs-info|needs author feedback|unconfirmed", labels, re.I)))
        delayed_or_stale = int(
            cycle_time_days >= DELAY_THRESHOLD_DAYS
            or (state == "open" and age_days >= DELAY_THRESHOLD_DAYS and time_since_update_days >= STALE_UPDATE_DAYS)
        )
        rows.append(
            {
                "program": item.get("_program"),
                "portfolio_domain": item.get("_portfolio_domain"),
                "source_repo": repo,
                "item_number": item.get("number"),
                "item_url": item.get("html_url"),
                "item_type": "Pull Request" if is_pr else "Issue",
                "title": title,
                "state": state,
                "created_at": created_at,
                "updated_at": updated_at,
                "closed_at": closed_at,
                "age_days": round(age_days, 2),
                "cycle_time_days": round(cycle_time_days, 2),
                "time_since_update_days": round(time_since_update_days, 2),
                "comment_count": int(item.get("comments") or 0),
                "label_count": len(labels.split(" | ")) if labels else 0,
                "labels": labels,
                "assignee_count": len(assignees),
                "has_milestone": int(milestone is not None),
                "locked": int(bool(item.get("locked"))),
                "author_association": item.get("author_association") or "NONE",
                "body_length": len(str(body)),
                "title_length": len(str(title)),
                "created_day_of_week": created_at.dayofweek,
                "created_month": created_at.month,
                "has_blocker_signal": has_blocker_signal,
                "has_bug_signal": has_bug_signal,
                "has_priority_signal": has_priority_signal,
                "has_triage_signal": has_triage_signal,
                "delayed_or_stale": delayed_or_stale,
                **repo_meta,
            }
        )

    frame = pd.DataFrame(rows)
    if frame.empty:
        raise ValueError("No GitHub Work Items Were Parsed.")
    return frame.sort_values("created_at").reset_index(drop=True)


def feature_columns() -> list[str]:
    return [
        "comment_count",
        "label_count",
        "assignee_count",
        "has_milestone",
        "locked",
        "body_length",
        "title_length",
        "created_day_of_week",
        "created_month",
        "has_blocker_signal",
        "has_bug_signal",
        "has_priority_signal",
        "has_triage_signal",
        "repo_stars",
        "repo_forks",
        "repo_open_issues",
        "repo_watchers",
        "repo_size",
        "program_code",
        "portfolio_domain_code",
        "source_repo_code",
        "item_type_code",
        "author_association_code",
    ]


def encode_features(frame: pd.DataFrame) -> pd.DataFrame:
    encoded = frame.copy()
    for column in ["program", "portfolio_domain", "source_repo", "item_type", "state", "author_association"]:
        encoded[f"{column}_code"] = encoded[column].astype("category").cat.codes
    for column in feature_columns():
        encoded[column] = pd.to_numeric(encoded[column], errors="coerce")
    encoded[feature_columns()] = encoded[feature_columns()].replace([np.inf, -np.inf], np.nan)
    encoded[feature_columns()] = encoded[feature_columns()].fillna(encoded[feature_columns()].median(numeric_only=True))
    return encoded


def safe_roc_auc(actual: pd.Series, predicted: np.ndarray) -> float:
    if actual.nunique() < 2:
        return 0.5
    return float(roc_auc_score(actual, predicted))


def safe_average_precision(actual: pd.Series, predicted: np.ndarray) -> float:
    if actual.nunique() < 2:
        return float(actual.mean())
    return float(average_precision_score(actual, predicted))


def train_risk_model(frame: pd.DataFrame) -> ModelArtifacts:
    encoded = encode_features(frame)
    features = feature_columns()
    split_index = max(int(len(encoded) * 0.76), 1)
    train = encoded.iloc[:split_index]
    test = encoded.iloc[split_index:]
    if train["delayed_or_stale"].nunique() < 2 or test["delayed_or_stale"].nunique() < 2:
        train, test = train_test_split(
            encoded,
            test_size=0.24,
            random_state=RANDOM_SEED,
            stratify=encoded["delayed_or_stale"],
        )

    model = HistGradientBoostingClassifier(
        learning_rate=0.08,
        max_iter=180,
        min_samples_leaf=24,
        l2_regularization=0.03,
        random_state=RANDOM_SEED,
    )
    model.fit(train[features], train["delayed_or_stale"])

    probabilities = model.predict_proba(test[features])[:, 1]
    thresholds = np.linspace(0.1, 0.75, 66)
    f1_values = [
        f1_score(test["delayed_or_stale"], (probabilities >= threshold).astype(int), zero_division=0)
        for threshold in thresholds
    ]
    best_threshold = float(thresholds[int(np.argmax(f1_values))])
    labels = (probabilities >= best_threshold).astype(int)

    metrics = pd.DataFrame(
        [
            {"model": "GitHub Program Delay Risk", "metric": "ROC AUC", "value": round(safe_roc_auc(test["delayed_or_stale"], probabilities), 4)},
            {"model": "GitHub Program Delay Risk", "metric": "Average Precision", "value": round(safe_average_precision(test["delayed_or_stale"], probabilities), 4)},
            {"model": "GitHub Program Delay Risk", "metric": "F1", "value": round(float(f1_score(test["delayed_or_stale"], labels, zero_division=0)), 4)},
            {"model": "GitHub Program Delay Risk", "metric": "Risk Threshold", "value": round(best_threshold, 3)},
            {"model": "GitHub Program Delay Risk", "metric": "Accuracy", "value": round(float(accuracy_score(test["delayed_or_stale"], labels)), 4)},
            {"model": "GitHub Program Delay Risk", "metric": "Training Rows", "value": int(len(train))},
            {"model": "GitHub Program Delay Risk", "metric": "Validation Rows", "value": int(len(test))},
            {"model": "GitHub Program Delay Risk", "metric": "Observed Delay Rate", "value": round(float(encoded["delayed_or_stale"].mean()), 4)},
        ]
    )

    sample_size = min(900, len(test))
    sample = test.sample(sample_size, random_state=RANDOM_SEED) if sample_size else test
    importance_scoring = "average_precision" if sample["delayed_or_stale"].nunique() > 1 else "accuracy"
    importance_result = permutation_importance(
        model,
        sample[features],
        sample["delayed_or_stale"],
        n_repeats=3,
        random_state=RANDOM_SEED,
        scoring=importance_scoring,
    )
    importance = pd.DataFrame(
        {
            "model": "GitHub Program Delay Risk",
            "feature": features,
            "importance": importance_result.importances_mean,
        }
    ).sort_values("importance", ascending=False)

    scored = frame.copy()
    all_probabilities = model.predict_proba(encoded[features])[:, 1]
    scored["delay_risk_probability"] = all_probabilities.round(4)
    scored["delay_risk_score"] = (all_probabilities * 100).round(1)
    scored["risk_level"] = pd.cut(
        scored["delay_risk_score"],
        bins=[-0.1, 35, 65, 100],
        labels=["Low", "Medium", "High"],
    ).astype(str)
    scored["recommended_action"] = scored.apply(make_item_action, axis=1)
    return ModelArtifacts(scored_items=scored, metrics=metrics, feature_importance=importance)


def make_item_action(row: pd.Series) -> str:
    if row["risk_level"] == "High" and row["has_blocker_signal"]:
        return "Escalate Blocker, Confirm Owner, And Add Executive Visibility This Week."
    if row["risk_level"] == "High" and row["item_type"] == "Pull Request":
        return "Fast-Track Review Path, Resolve Review Bottlenecks, And Confirm Merge Readiness."
    if row["risk_level"] == "High":
        return "Move To PMO Watchlist, Validate Scope, Owner, And Next Decision Date."
    if row["risk_level"] == "Medium":
        return "Monitor Aging, Confirm Milestone Fit, And Refresh Status Evidence."
    return "Keep In Normal Delivery Rhythm."


def build_program_health(scored: pd.DataFrame) -> pd.DataFrame:
    closed = scored[scored["closed_at"].notna()].copy()
    cycle_lookup = closed.groupby(["program", "source_repo"], as_index=False).agg(
        avg_cycle_time_closed=("cycle_time_days", "mean"),
        median_cycle_time_closed=("cycle_time_days", "median"),
    )
    summary = (
        scored.groupby(["program", "portfolio_domain", "source_repo"], as_index=False)
        .agg(
            total_work_items=("item_number", "count"),
            open_work_items=("state", lambda values: int((values == "open").sum())),
            pull_requests=("item_type", lambda values: int((values == "Pull Request").sum())),
            issues=("item_type", lambda values: int((values == "Issue").sum())),
            avg_delay_risk_score=("delay_risk_score", "mean"),
            high_risk_items=("risk_level", lambda values: int((values == "High").sum())),
            blocker_signals=("has_blocker_signal", "sum"),
            stale_or_delayed_rate=("delayed_or_stale", "mean"),
            avg_time_since_update_days=("time_since_update_days", "mean"),
            repo_stars=("repo_stars", "max"),
        )
        .merge(cycle_lookup, on=["program", "source_repo"], how="left")
    )
    summary["open_rate"] = summary["open_work_items"] / summary["total_work_items"].clip(lower=1)
    risk_penalty = summary["avg_delay_risk_score"] * 0.42
    open_penalty = summary["open_rate"] * 24
    blocker_penalty = np.minimum(summary["blocker_signals"] * 2.8, 18)
    stale_penalty = summary["avg_time_since_update_days"].clip(upper=60) * 0.18
    summary["program_health_score"] = (100 - risk_penalty - open_penalty - blocker_penalty - stale_penalty).clip(0, 100).round(1)
    summary["program_status"] = pd.cut(
        summary["program_health_score"],
        bins=[-0.1, 55, 78, 100],
        labels=["Red", "Amber", "Green"],
    ).astype(str)
    return summary.round(
        {
            "avg_delay_risk_score": 2,
            "stale_or_delayed_rate": 4,
            "avg_time_since_update_days": 2,
            "avg_cycle_time_closed": 2,
            "median_cycle_time_closed": 2,
            "open_rate": 4,
        }
    ).sort_values(["program_health_score", "avg_delay_risk_score"], ascending=[True, False])


def build_action_queue(scored: pd.DataFrame) -> pd.DataFrame:
    queue = scored.sort_values(["delay_risk_score", "time_since_update_days", "comment_count"], ascending=[False, False, False]).head(50).copy()
    queue["decision_lane"] = np.select(
        [
            queue["has_blocker_signal"].eq(1),
            queue["item_type"].eq("Pull Request"),
            queue["has_bug_signal"].eq(1),
            queue["has_priority_signal"].eq(1),
        ],
        ["Dependency / Blocker", "Delivery Review", "Quality Risk", "Priority Escalation"],
        default="Program Watchlist",
    )
    return queue[
        [
            "decision_lane",
            "program",
            "source_repo",
            "item_type",
            "item_number",
            "title",
            "state",
            "risk_level",
            "delay_risk_score",
            "age_days",
            "time_since_update_days",
            "comment_count",
            "labels",
            "item_url",
            "recommended_action",
        ]
    ]


def build_dependency_view(scored: pd.DataFrame) -> pd.DataFrame:
    dependency = scored[
        scored["has_blocker_signal"].eq(1)
        | scored["has_triage_signal"].eq(1)
        | scored["labels"].str.contains("dependency|blocked|waiting|needs", case=False, na=False)
    ].copy()
    if len(dependency) < 20:
        dependency = pd.concat([dependency, scored.sort_values("delay_risk_score", ascending=False).head(30)], ignore_index=True)
    dependency["dependency_signal"] = np.select(
        [
            dependency["has_blocker_signal"].eq(1),
            dependency["has_triage_signal"].eq(1),
            dependency["has_priority_signal"].eq(1),
        ],
        ["Blocker Or External Dependency", "Needs Triage Or Clarification", "Priority Escalation"],
        default="Potential Delivery Dependency",
    )
    return dependency.drop_duplicates(["source_repo", "item_number"]).sort_values("delay_risk_score", ascending=False).head(40)[
        [
            "dependency_signal",
            "program",
            "source_repo",
            "item_type",
            "item_number",
            "title",
            "risk_level",
            "delay_risk_score",
            "time_since_update_days",
            "labels",
            "item_url",
        ]
    ]


def build_flow_timeline(scored: pd.DataFrame) -> pd.DataFrame:
    frame = scored.copy()
    frame["created_month_start"] = frame["created_at"].dt.tz_convert(None).dt.to_period("M").dt.to_timestamp().astype(str)
    frame["closed_month_start"] = frame["closed_at"].dt.tz_convert(None).dt.to_period("M").dt.to_timestamp().astype(str)
    created = (
        frame.groupby(["created_month_start", "program"], as_index=False)
        .agg(created_items=("item_number", "count"), created_high_risk=("risk_level", lambda values: int((values == "High").sum())))
        .rename(columns={"created_month_start": "month"})
    )
    closed = (
        frame[frame["closed_at"].notna()]
        .groupby(["closed_month_start", "program"], as_index=False)
        .agg(closed_items=("item_number", "count"))
        .rename(columns={"closed_month_start": "month"})
    )
    timeline = created.merge(closed, on=["month", "program"], how="left").fillna({"closed_items": 0})
    timeline["closed_items"] = timeline["closed_items"].astype(int)
    timeline["throughput_gap"] = timeline["created_items"] - timeline["closed_items"]
    return timeline.sort_values(["month", "program"])


def build_status_briefs(program_health: pd.DataFrame, action_queue: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in program_health.iterrows():
        program_actions = action_queue[action_queue["program"].eq(row["program"])]
        top_lane = program_actions["decision_lane"].iloc[0] if not program_actions.empty else "Program Watchlist"
        brief = (
            f"{row['program']} Is {row['program_status']} With A Health Score Of {row['program_health_score']}. "
            f"The Highest PMO Signal Is {top_lane}, With {int(row['high_risk_items'])} High-Risk Work Items "
            f"And {int(row['blocker_signals'])} Dependency Or Blocker Signals."
        )
        evidence = (
            f"{int(row['total_work_items'])} Items Scored; "
            f"{int(row['open_work_items'])} Open; "
            f"{row['avg_delay_risk_score']:.1f} Average Risk; "
            f"{row['stale_or_delayed_rate']:.1%} Delayed Or Stale."
        )
        if row["program_status"] == "Red":
            focus = "Run A PMO Recovery Review, Confirm Owners, And Protect Near-Term Milestones."
        elif row["program_status"] == "Amber":
            focus = "Tighten Status Evidence, Clear Aging Items, And Watch Dependency Signals."
        else:
            focus = "Maintain Governance Rhythm And Reuse The Program As A Healthy Delivery Pattern."
        rows.append(
            {
                "program": row["program"],
                "program_status": row["program_status"],
                "status_brief": brief,
                "evidence": evidence,
                "recommended_focus": focus,
            }
        )
    return pd.DataFrame(rows)


def build_executive_kpis(scored: pd.DataFrame, program_health: pd.DataFrame, metrics: pd.DataFrame) -> pd.DataFrame:
    metric_lookup = metrics.set_index("metric")["value"].to_dict()
    return pd.DataFrame(
        [
            {
                "project_owner": "Pratheepa Gobady",
                "data_source": "GitHub REST API Public Issues And Pull Requests",
                "programs_analyzed": int(program_health["program"].nunique()),
                "repositories_analyzed": int(scored["source_repo"].nunique()),
                "work_items_scored": int(len(scored)),
                "open_work_items": int((scored["state"] == "open").sum()),
                "high_risk_work_items": int((scored["risk_level"] == "High").sum()),
                "avg_delay_risk_score": round(float(scored["delay_risk_score"].mean()), 2),
                "at_risk_programs": int(program_health["program_status"].isin(["Red", "Amber"]).sum()),
                "blocker_dependency_signals": int(scored["has_blocker_signal"].sum()),
                "model_roc_auc": metric_lookup.get("ROC AUC"),
                "model_average_precision": metric_lookup.get("Average Precision"),
                "model_f1": metric_lookup.get("F1"),
            }
        ]
    )


def frame_to_records(frame: pd.DataFrame, limit: int | None = None) -> list[dict[str, object]]:
    data = frame.head(limit).copy() if limit else frame.copy()
    data = data.replace([np.inf, -np.inf], np.nan)
    data = data.where(pd.notna(data), None)
    for column in data.select_dtypes(include=["datetimetz", "datetime64[ns]", "datetime64[ns, UTC]"]).columns:
        data[column] = data[column].astype(str)
    return data.to_dict(orient="records")


def build_web_payload(
    executive_kpis: pd.DataFrame,
    program_health: pd.DataFrame,
    action_queue: pd.DataFrame,
    dependency_view: pd.DataFrame,
    flow_timeline: pd.DataFrame,
    status_briefs: pd.DataFrame,
    metrics: pd.DataFrame,
    importance: pd.DataFrame,
) -> dict[str, object]:
    recent_months = sorted(flow_timeline["month"].unique())[-12:]
    recent_flow = flow_timeline[flow_timeline["month"].isin(recent_months)].copy()
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generatedFor": "Pratheepa Gobady",
        "title": "AI PMO & Program Control Tower",
        "kpis": frame_to_records(executive_kpis)[0],
        "programHealth": frame_to_records(program_health),
        "actionQueue": frame_to_records(action_queue, 32),
        "dependencyView": frame_to_records(dependency_view, 28),
        "flowTimeline": frame_to_records(recent_flow),
        "statusBriefs": frame_to_records(status_briefs),
        "modelMetrics": frame_to_records(metrics),
        "featureImportance": frame_to_records(importance.head(18)),
    }


def write_outputs(
    scored: pd.DataFrame,
    program_health: pd.DataFrame,
    action_queue: pd.DataFrame,
    dependency_view: pd.DataFrame,
    flow_timeline: pd.DataFrame,
    status_briefs: pd.DataFrame,
    executive_kpis: pd.DataFrame,
    metrics: pd.DataFrame,
    importance: pd.DataFrame,
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)

    scored_output = scored.copy()
    for column in ["created_at", "updated_at", "closed_at"]:
        scored_output[column] = scored_output[column].astype(str)
    scored_output.to_csv(OUTPUT_DIR / "work_item_risk_predictions.csv", index=False)
    program_health.to_csv(OUTPUT_DIR / "program_health_summary.csv", index=False)
    action_queue.to_csv(OUTPUT_DIR / "risk_action_queue.csv", index=False)
    dependency_view.to_csv(OUTPUT_DIR / "dependency_blocker_view.csv", index=False)
    flow_timeline.to_csv(OUTPUT_DIR / "portfolio_flow_timeline.csv", index=False)
    status_briefs.to_csv(OUTPUT_DIR / "executive_status_briefs.csv", index=False)
    executive_kpis.to_csv(OUTPUT_DIR / "executive_kpis.csv", index=False)
    metrics.to_csv(OUTPUT_DIR / "model_metrics.csv", index=False)
    importance.to_csv(OUTPUT_DIR / "feature_importance.csv", index=False)

    payload = build_web_payload(
        executive_kpis,
        program_health,
        action_queue,
        dependency_view,
        flow_timeline,
        status_briefs,
        metrics,
        importance,
    )
    (WEB_DATA_DIR / "dashboard_data.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (WEB_DATA_DIR / "dashboard_data.js").write_text(
        "window.PMO_CONTROL_TOWER_DATA = " + json.dumps(payload, indent=2) + ";\n",
        encoding="utf-8",
    )


def main() -> None:
    require_files()
    raw_items = load_json(RAW_DIR / "github_work_items.json")
    raw_metadata = load_json(RAW_DIR / "repository_metadata.json")
    if not isinstance(raw_items, list) or not isinstance(raw_metadata, list):
        raise TypeError("Raw GitHub Payloads Must Be Lists.")

    print("Building Real GitHub PMO Work Item Frame...", flush=True)
    frame = flatten_work_items(raw_items, raw_metadata)
    print(f"Training Delay-Risk Model On {len(frame):,} Work Items...", flush=True)
    artifacts = train_risk_model(frame)
    print("Building Program Health, Dependency, And Executive Brief Outputs...", flush=True)
    program_health = build_program_health(artifacts.scored_items)
    action_queue = build_action_queue(artifacts.scored_items)
    dependency_view = build_dependency_view(artifacts.scored_items)
    flow_timeline = build_flow_timeline(artifacts.scored_items)
    status_briefs = build_status_briefs(program_health, action_queue)
    executive_kpis = build_executive_kpis(artifacts.scored_items, program_health, artifacts.metrics)
    write_outputs(
        artifacts.scored_items,
        program_health,
        action_queue,
        dependency_view,
        flow_timeline,
        status_briefs,
        executive_kpis,
        artifacts.metrics,
        artifacts.feature_importance,
    )

    print("AI PMO Control Tower Outputs Created:")
    for path in sorted(OUTPUT_DIR.glob("*.csv")):
        print(f"- {path}")
    print(f"- {WEB_DATA_DIR / 'dashboard_data.json'}")
    print("\nExecutive KPIs:")
    print(executive_kpis.to_string(index=False))


if __name__ == "__main__":
    main()
