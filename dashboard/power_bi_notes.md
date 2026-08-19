# Power BI Build Notes

Import These Files From The `outputs/` Folder:

- `executive_kpis.csv`
- `program_health_summary.csv`
- `work_item_risk_predictions.csv`
- `risk_action_queue.csv`
- `dependency_blocker_view.csv`
- `portfolio_flow_timeline.csv`
- `executive_status_briefs.csv`
- `model_metrics.csv`
- `feature_importance.csv`

## Suggested Report Pages

1. Executive PMO Control Tower
   - Cards: Programs Analyzed, Work Items Scored, High-Risk Work Items, Model ROC AUC.
   - Table: Program Health Summary Sorted By Lowest Health Score.
   - KPI Band: At-Risk Programs And Blocker/Dependency Signals.

2. Program Health And Delivery Risk
   - Scatter Chart: Program Health Score Vs Average Delay Risk Score.
   - Bar Chart: High-Risk Items By Program.
   - Matrix: Open Work Items, Open Rate, Stale/Delayed Rate, Blocker Signals.

3. PMO Action Queue
   - Table: `risk_action_queue` With Risk Level, Decision Lane, Recommended Action, And URL.
   - Slicers: Program, Source Repo, Risk Level, Decision Lane, Item Type.

4. Dependency And Blocker Radar
   - Table: `dependency_blocker_view`.
   - Bar Chart: Dependency Signals By Program.
   - Card: Items With Blocker Or External Dependency Signals.

5. Flow And Throughput
   - Line/Column Combo: Created Items Vs Closed Items By Month.
   - Bar Chart: Throughput Gap By Program.
   - Slicer: Program.

6. Model Explainability
   - Bar Chart: Feature Importance.
   - Cards: ROC AUC, Average Precision, F1, Accuracy, Observed Delay Rate.

## Suggested Relationships

- `program_health_summary[program]` To `work_item_risk_predictions[program]`
- `program_health_summary[program]` To `risk_action_queue[program]`
- `program_health_summary[program]` To `dependency_blocker_view[program]`
- `program_health_summary[program]` To `portfolio_flow_timeline[program]`
- `program_health_summary[program]` To `executive_status_briefs[program]`

## Useful DAX Measures

```DAX
Work Items Scored = COUNTROWS(work_item_risk_predictions)

High Risk Work Items =
CALCULATE(
    COUNTROWS(work_item_risk_predictions),
    work_item_risk_predictions[risk_level] = "High"
)

Average Delay Risk = AVERAGE(work_item_risk_predictions[delay_risk_score])

Average Program Health = AVERAGE(program_health_summary[program_health_score])

At Risk Programs =
CALCULATE(
    DISTINCTCOUNT(program_health_summary[program]),
    program_health_summary[program_status] IN {"Red", "Amber"}
)

Throughput Gap =
SUM(portfolio_flow_timeline[created_items]) - SUM(portfolio_flow_timeline[closed_items])
```
