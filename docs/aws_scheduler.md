# AWS EventBridge Scheduler — setup guide

This replaces GitHub Actions native cron (which is best-effort and frequently
delays or drops scheduled runs under load) with AWS EventBridge invoking the
existing `workflow_dispatch` triggers in `daily_pipeline.yml` and
`refresh_picks.yml`.

The CloudFormation template lives at `infra/aws_scheduler.yaml`. Total cost
for our workload (~150 invocations/month) is **$0** — well inside the AWS
free tier.

## Architecture

```
EventBridge Rule (cron)  ->  API Destination  ->  Connection (PAT)  ->  GitHub API
```

Five rules total, one per slot: 7am, 12pm, 3pm, 6pm, 8pm ET. Each one POSTs
to the corresponding workflow's `dispatches` endpoint with `{"ref": "master"}`.

## One-time setup

### 1. Create a GitHub fine-grained PAT

1. Go to https://github.com/settings/personal-access-tokens
2. Click **Generate new token (fine-grained)**
3. **Repository access**: Only select repositories -> `MJACode/betting-model`
4. **Repository permissions**:
   - **Actions**: Read and write
   - **Metadata**: Read-only (auto-selected)
5. **Expiration**: 1 year (renew via the same flow when it expires; update
   the EventBridge Connection with the new PAT)
6. Generate and copy the token. You'll paste it into CloudFormation in step 3.

### 2. Create the AWS account (if you don't have one)

1. Sign up at https://aws.amazon.com — has a generous free tier.
2. Create an IAM user with admin or PowerUser access for yourself (don't use
   the root account day-to-day).

### 3. Deploy the CloudFormation stack

From the AWS Console:
1. Go to **CloudFormation** -> **Create stack** -> **With new resources**
2. **Template source**: Upload a template file -> select `infra/aws_scheduler.yaml`
3. **Stack name**: `betting-model-scheduler`
4. **Parameters**:
   - `GitHubPat`: paste the token from step 1
   - `GitHubRepoOwner`: `MJACode`
   - `GitHubRepoName`: `betting-model`
   - `GitRef`: `master`
5. **Capabilities**: check the IAM acknowledgement box (the stack creates a role)
6. Create stack. Takes ~1 minute.

Or via the AWS CLI:
```bash
aws cloudformation deploy \
  --stack-name betting-model-scheduler \
  --template-file infra/aws_scheduler.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides GitHubPat=<paste-token-here>
```

### 4. Verify

In the AWS Console:
1. Go to **EventBridge** -> **Rules** -> select `betting-model-daily-pipeline-7am-et`
2. Click **Actions** -> **Edit** -> **Send test event** (or wait for the next
   scheduled trigger)
3. Confirm a new run shows up in
   https://github.com/MJACode/betting-model/actions

If the GitHub run doesn't appear:
- **CloudWatch Logs** under `/aws/events/...` shows API destination invocation
  failures. Common causes: PAT expired/missing scope, wrong repo name.
- Check the **Connection** resource in EventBridge — if the auth header is
  malformed it will say so.

### 5. Disable GitHub Actions native cron

Once you've seen 24 hours of clean runs from EventBridge, edit
`.github/workflows/daily_pipeline.yml` and `refresh_picks.yml` to remove the
`schedule:` block, keeping only `workflow_dispatch:`. This stops double-firing.

## Maintenance

### PAT renewal

Fine-grained PATs expire (max 1 year). When it expires:
1. Generate a new PAT (same scope as step 1).
2. **EventBridge** -> **API destinations** -> **Connections** -> select
   `betting-model-github-pat` -> **Edit** -> paste new PAT into the API key
   value field. Save.

(Or update the parameter and redeploy the CloudFormation stack.)

### Adding new schedules

E.g. when you add a props pipeline that should run at 9am ET, add a new
`AWS::Events::Rule` resource in `infra/aws_scheduler.yaml` and redeploy.

### Failure notifications

Optional follow-up: subscribe an SNS topic to EventBridge's "rule failed to
invoke target" event and get an email/SMS when a rule fails. Not included in
the base template.

## Why this over alternatives

| Option | Reliability | Cost | Why we chose / didn't |
|---|---|---|---|
| **GitHub Actions cron** | Best-effort (30-90 min delay typical, occasionally dropped) | Free | Currently in use; the problem we're solving. |
| **cron-job.org / EasyCron** | Good (~99.95% SLA on free tier) | Free | Works fine, but no path to grow into Lambda/SNS/etc. as the system expands. |
| **Railway cron** | Good | ~$5/mo | Fine if we move pipeline execution to Railway. Doesn't help if execution stays on GitHub Actions. |
| **AWS EventBridge** | Excellent (99.99% SLA) | Free tier covers it | Chosen — also gives us a path to Lambda for future props pipelines. |
