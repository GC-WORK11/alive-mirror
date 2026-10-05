# AWS console shotlist — the mandatory beat

**Risk flag:** the hackathon demo video *must show the AWS console* — a video
without it is disqualified. This is the only beat Devin cannot film (it needs
the owner's AWS login), so the owner records this 25 s slot himself on demo
morning. It is beat 6 (2:05–2:30) in `docs/submission/video-shotlist.md`.

Save the clip as **`~/video/beats/80_aws.mov`** (or `.mp4`) — `scripts/video/assemble.sh`
slots it into the timeline automatically. Any screen recorder works; QuickTime
`⌘⇧5` → "Record Selected Portion" is fine. Hide the bookmarks bar, console at
125% zoom, full region `ap-south-1` pinned (region selector top-right).

Before filming, open a terminal and run
`curl -s http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com/health | grep build_sha`
— ideally the image tag you show equals this `build_sha`. **Known wart
(2026-10-05, re-checked ~19:30 UTC):** `/health` currently stamps
`6e82f290`, matching the deployed image — the lag wart is resolved on
this revision but has recurred across deploys today (`c7df5db5` vs
`1e93b9f2`, `cb862533` vs `ec51c882`). The console tag is the truth;
if `/health` disagrees, show the ECR/task image URI and say the deploy
revision, not the stamp. It bumps on every deploy.

## What each frame must show to score

| # | Console page | Must visibly show | ~secs |
|---|--------------|-------------------|-------|
| 1 | ECS → cluster `alive108` → service `alive108` | **Service status ACTIVE**, **Desired/Running tasks 1/1**, launch type **FARGATE** (see note below) | 6 |
| 2 | Service → "Tasks" tab → running task → task definition | **Image URI** `…/alive108:<build_sha>` matching `/health`, CPU/memory, env block | 6 |
| 3 | CloudWatch → Log groups → `/ecs/alive108` → latest stream | Fresh log lines with today's timestamps — proves it's really serving | 5 |
| 4 | CodeBuild → build history | Last build **Succeeded**, duration, commit hash matching repo HEAD | 4 |
| 5 | EC2 → Load Balancers → the NLB → Listeners + Target Groups | Listener `:80` forwarding; target group **healthy targets 1/1** | 4 |

## Numbered click-path (say it as you go)

1. Console home → search bar type **ECS** → Clusters → `alive108` → service
   `alive108`. Pause 2 s on the green **ACTIVE** + **1/1** row.
   Say: *"The engine runs on ECS Fargate behind a Network Load Balancer."*
2. Same page → **Tasks** tab → click the running task → scroll to **Container
   details → Image URI**. The tag must equal today's `build_sha`.
   Say: *"Every deploy ships a tagged image — this tag is the live build."*
3. Task detail → **Logs** tab (or CloudWatch → log group `/ecs/alive108`) →
   newest stream. Let the tail scroll — field-refresh lines land every ~15 min.
   Say: *"CloudWatch tails the engine live."*
4. Search **CodeBuild** → project `alive108` → **Build history** → top row
   **Succeeded**.
   Say: *"CodeBuild rebuilds and redeploys on every push."*
5. Search **EC2** → left rail **Load Balancers** → `alive108-…` NLB →
   **Listeners** (`:80 → target group`) → **Target groups** → **Targets** tab →
   **Healthy**.
   Say: *"The NLB fronts it; the target's healthy — that's the site you just saw."*

Total ~25 s of console on camera. If a page is slow, keep rolling — load
spinner on a real console reads as more authentic than a cut.

## Notes

- **FARGATE vs FARGATE_SPOT:** `docs/demo-day.md` has the SPOT→FARGATE flip for
  judging morning. Whichever capacity provider is live at film time is fine —
  say "Fargate" on camera either way.
- Do **not** blur or crop anything except the account ID (top-right) — judges
  look for real timestamps and real ARNs.
- If the service shows **0/1** or **DRAINING**, stop — flip it back first
  (`docs/demo-day.md` runbook), then re-film. Filming a drained service scores
  worse than skipping the beat.
