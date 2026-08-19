# AI PMO & Program Control Tower

**Live Dashboard:** [Open AI PMO & Program Control Tower](https://pratheepagobady15.github.io/AI-PMO-Program-Control-Tower/)

An Advanced Real-Data Program Management Control Tower Built For Pratheepa Gobady.
It Uses Public GitHub Project Signals To Predict Work-Item Risk, Summarize Program Health, Surface Dependency Blockers, And Create Executive-Ready Status Evidence.
The Project Combines A Working ML Pipeline, Power BI-Ready Outputs, And A Visually Distinct Browser Dashboard For Recruiter Review.

This Project Turns Public GitHub Issues And Pull Requests Into A Portfolio-Level PMO Dashboard With Predictive Delay Risk, Program Health Scoring, Dependency Signals, Executive Status Briefs, And Power BI-Ready Outputs.

## What Makes It Different

Most PMO Dashboards Show Static Status. This Project Acts Like A Predictive Program Control Tower:

- Uses Real Public GitHub Issues And Pull Requests Instead Of Fake Project Rows.
- Scores Work Items Across Multiple Large Public Repositories Treated As Program Streams.
- Trains A Working Delay-Risk Classifier With Holdout Validation.
- Builds Program Health Scores From Risk, Open Work, Staleness, Blockers, And Throughput Signals.
- Creates Evidence-Backed Executive Status Briefs From Model Outputs And Program Metrics.
- Produces A Futuristic Browser Dashboard And Clean CSV Files For Power BI.

## Default Program Streams

- Developer Experience Modernization: `microsoft/vscode`
- Cloud Native Platform Reliability: `kubernetes/kubernetes`
- Data Platform Orchestration: `apache/airflow`
- Runtime Platform Stabilization: `nodejs/node`
- Language Ecosystem Delivery: `rust-lang/rust`

## Project Outputs

```text
outputs/
  work_item_risk_predictions.csv
  program_health_summary.csv
  risk_action_queue.csv
  dependency_blocker_view.csv
  portfolio_flow_timeline.csv
  executive_status_briefs.csv
  executive_kpis.csv
  model_metrics.csv
  feature_importance.csv

web/
  index.html
  styles.css
  app.js
  data/dashboard_data.js
```

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Run The Real-Data Pipeline

```powershell
python src\download_real_data.py
python src\build_real_data_outputs.py
```

The Download Script Works Without A Token For Small Pulls. If GitHub API Limits Are Hit, Set A `GITHUB_TOKEN` Environment Variable And Run It Again.

## Validate The Project

```powershell
python tests\validate_real_data_outputs.py
```

The Validation Script Checks Required Outputs, Real GitHub Source Signals, Model Metrics, Risk Scores, Program Health Scores, Dashboard JSON, And Download-Ready Data Products.

## Open The Dashboard

Open The Live Dashboard:

```text
https://pratheepagobady15.github.io/AI-PMO-Program-Control-Tower/
```

Or Open This File Locally In A Browser:

```text
web/index.html
```

For A Local HTTP Preview From The Project Root:

```powershell
python -m http.server 8770 --bind 127.0.0.1
```

Then Open:

```text
http://127.0.0.1:8770/web/index.html
```

## Portfolio Story

**AI PMO & Program Control Tower** - A Real-Data AI Program Management Dashboard That Uses Public GitHub Work Items To Predict Delivery Risk, Score Program Health, Surface Dependency Signals, And Generate Executive Status Briefs.

Recommended Resume Bullets:

- Built A Real-Data AI PMO Control Tower Using Public GitHub Issues And Pull Requests Across Five Large Open-Source Program Streams.
- Trained A Delay-Risk Classification Model To Score Work Items And Identify High-Risk Delivery Items.
- Designed Program Health Scoring, Dependency Detection, Executive Status Briefs, And A Ranked PMO Action Queue.
- Created A Visually Advanced Browser Dashboard And Power BI-Ready Data Products For Portfolio-Level Delivery Governance.
