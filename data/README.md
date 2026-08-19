# Data Sources

This Project Uses Real Public GitHub Data. Raw API Responses Are Not Committed Because They Can Be Rebuilt.

## Source

- GitHub REST API: https://docs.github.com/en/rest
- Business Use: Real Work Items, Pull Requests, Issue Aging, Delivery Risk, Program Health, Dependency Signals, And Executive PMO Status Briefs.

## Public Repositories Used By Default

- `microsoft/vscode`
- `kubernetes/kubernetes`
- `apache/airflow`
- `nodejs/node`
- `rust-lang/rust`

These Repositories Are Treated As Program Streams For A Portfolio-Level PMO Control Tower.

## Expected Local Layout

```text
data/
  raw/
    github_work_items.json
    repository_metadata.json
```

Run This To Rebuild Raw Data:

```powershell
python src\download_real_data.py
```

The Script Works Without A Token For Small Pulls, But A `GITHUB_TOKEN` Environment Variable Can Be Added For Higher API Limits.
