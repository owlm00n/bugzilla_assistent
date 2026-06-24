# Log Analysis Prompt Template

## Role-Based Log Analysis

You are a {role_name} analyzing a log file. Based on your role context, follow these guidelines:

### Your Role Context
```yaml
{role_yaml}
```

### Log Content
```
{log_content}
```

### Analysis Task

1. **Log Type Detection**: Identify the log type (PD negotiation / USB enumeration / dmesg / mixed)

2. **Role-Based Filtering**: Using your {role_name} perspective, focus on:
   - Keywords from your focus list: {focus_keywords}
   - Modules you care about: {concern_modules}
   - Your search strategy: {search_strategy}

3. **Anomaly Detection**: Find and highlight all anomalies with severity levels:
   - CRITICAL: System crash, hard fault, data corruption
   - ERROR: Functional failure, timeout, protocol error
   - WARNING: Degraded performance, retry, unusual behavior
   - INFO: Notable events worth tracking

4. **Timeline Reconstruction**: Build a timeline of key events relevant to your role

5. **Root Cause Analysis**: Based on the evidence, provide:
   - Most likely root cause
   - Contributing factors
   - Evidence supporting each hypothesis

6. **Actionable Recommendations**: Specific next steps for your role

### Output Format
```
## Log Summary
- Type: [detected type]
- Duration: [time span]
- Key Events: [number]

## Anomalies Found
### CRITICAL
- ...
### ERROR
- ...
### WARNING
- ...

## Timeline (Role-Relevant)
| Time | Event | Relevance |
|------|-------|-----------|

## Root Cause Analysis
[Your analysis]

## Recommendations
[Your recommendations]
```
