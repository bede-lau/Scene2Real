# Portable backend hosting QA — 18 October 2026

> The sections below record the original 18 October deployment. The 25 October
> Vercel/Railway cloud verification is recorded at the end of this document.

## Scope

Package the existing Python/MuJoCo backend for a persistent Linux container,
while keeping the public interface on its existing ChatGPT Sites URL. Model
prompts, frames, inference settings, and simulation behavior are unchanged.
Runtime API credentials and user run data are excluded from the image.

The container runs one Uvicorn worker on loopback behind the authenticated
Node proxy. It uses software OSMesa rendering, a writable `/data` volume,
unprivileged application processes, process supervision, and a health check.
The health endpoint checks local process availability; it does not claim that
external model services are working.

## Automated verification

- Docker builds succeeded for Linux ARM64 and Linux AMD64.
- The final pinned image passed all **180 Python tests** on ARM64 (29.10 s)
  and AMD64 (80.47 s under local emulation). These include real MuJoCo video
  rendering and FFmpeg encoding/failure handling.
- All **4 Node proxy tests** passed in Linux, covering authentication, request
  target pinning, truncated upstream streams, client disconnects, health
  propagation, and compressed upstream responses.
- Shell syntax checks and `git diff --check` passed.
- The Linux systemd installer was reviewed for service ownership, isolated
  ports, private configuration, a single worker, and persistent storage. It
  refuses to replace another deployment's units. It has not been executed on
  the workshop VM.

## Live container smoke test

The final container used the existing private runtime configuration mounted
read-only. No credentials were copied into the build context.

1. `/healthz` returned 200; unauthenticated `/api/clips` returned 401.
2. Authenticated API calls found all seven demo clips and an available G1 model.
3. A fresh `demo-set-1-west` run completed live Cosmos plus Astra spatial review
   in **32.38 s**, producing four fire sightings. This single-view measurement
   is a deployment smoke test, not a comparison with earlier multiview timings.
4. One sighting was explicitly confirmed as a template target; the remaining
   sightings were excluded with a QA reason. Astra planning completed in
   **5.06 s**.
5. MuJoCo simulation and MP4 export completed in **8.09 s**, with success and
   zero unintended collisions. The authenticated video download was 37,099 bytes.
6. After restarting the whole container, the saved run remained completed and
   the downloaded video matched its original SHA-256 hash.
7. With the QA container's restart policy enabled, forcibly terminating its
   backend caused supervision to stop the container. Docker automatically
   restarted it, and the authenticated saved run was still completed.

The test container was healthy and used approximately 587 MiB while idle after
this flow. This is an observation, not a resource or hosting-cost guarantee.

## Production status and cutover

The previous Quick Tunnel stopped registering with Cloudflare (`Unauthorized:
Tunnel not found`), while both local backend services remained healthy. The
existing Site was redeployed with a replacement temporary route and runtime
environment revision 4. Authenticated Site requests returned 200 for all seven
clips and the G1 model configuration after recovery.

A permanent managed-host deployment is pending a hosting account and spending
limit. No paid service has been created. The current Mac route remains a
temporary fallback; the backend has not moved to the workshop VM. SSH access
requires a fresh Cloudflare Access login, and no OTP arrived in the available
mailbox after the login request.

Before permanent cutover, attach `/data` storage, transfer prior `runs/` data
securely, configure runtime secrets, and repeat the authenticated model and
render smoke test at the chosen host. Then update only the Sites backend URL
and redeploy the existing interface. Keep one instance: saved runs survive
restarts, but active operations and in-memory live sessions must be retried.

## Vercel / Railway Hobby — 25 October 2026

The isolated `mindful-reverence` project now runs the backend on Railway Hobby:
one vCPU, one replica, 1 GB RAM, `/data` on a 5 GB persistent volume, with the
existing $10 compute spending cap retained. The active source deployment is
`260466d3-4a42-40a1-bc50-155fd054a010`, pinned to hosting-branch commit
`89fdb16a778c33dd681808eedc8525bfb888c328`. It uses OSMesa/llvmpipe and one
FFmpeg/BLAS/OSMesa thread. A direct cgroup read confirmed a 999,997,440-byte
memory limit and zero OOM events. Merely saving the resource configuration
and reusing the old Free build had left the old runtime at 500 MB; a fresh
source deployment was required. Railway metrics now also report the 1 GB limit.

The Vercel workbench is deployed at:
`https://scene2real-workbench-trial-fkkkvec4c-emanate-projects.vercel.app`.
It keeps the current `main` UI and report modules, with an additional upload
transport for larger selections. Vercel stores only the backend origin and a
private service token. Model credentials exist only on Railway. Deployment
Protection remains enabled: an unauthenticated API request redirects to Vercel
sign-in. The generated public production alias was removed from the test
project, and no public alias was added for this deployment.

### Fresh cloud pipeline tests

| Fixture | Run | Targets suppressed | Collisions | MP4 duration | MP4 bytes |
| --- | --- | --- | --- | --- | --- |
| Warehouse set 1 | `r_20261025_021945_c8a4` | 4 / 4 | 0 | 33.233333 s | 146,464 |
| Warehouse set 2 | `r_20261025_021333_7d7c` | 3 / 3 | 0 | 27.166667 s | 134,118 |

Each test uploaded three videos, performed uncached live Cosmos analysis,
confirmed authored template targets from the V1 view, generated a real Astra
plan, and ran the measured simulation. All observations stayed unchanged
through confirmation, planning and rendering. MP4s downloaded through Vercel
and decoded using FFmpeg/ffprobe. Other-camera sightings were explicitly
excluded with a hosting-QA reason: these tests do not establish cross-camera
identity accuracy or calibrated world coordinates. Set 2 ran on the verified
1 GB deployment immediately preceding the upload-transport deployment;
Set 1 exercised the final upload-transport deployment.

### Upload, persistence and interface checks

- A valid MP4 padded to 6 MiB initially returned Vercel HTTP 413
  `FUNCTION_PAYLOAD_TOO_LARGE`. The cloud upload path now obtains a two-minute,
  origin-bound single-use grant over the authenticated gateway and sends the
  multipart body directly to Railway. The Set 1 test used that larger file
  with two further camera views. A replay returned 401. Reusable service and
  model credentials are never sent to the browser.
- Seven Node tests passed, including grant expiry, origin binding, replay,
  scoped API access, request-size rejection, streaming, authentication,
  disconnected clients and range responses. The grant route is disabled
  unless `SCENE2REAL_PUBLIC_ORIGIN` is configured.
- The 11 gateway checks passed against the Vercel deployment, including health,
  all seven clips, three-view upload, the unchanged report module, protected
  private paths, saved runs, and a 206 MP4 range response.
- Three prior completed runs retained identical metrics and recording hashes
  after the necessary source deployment, including the completed Set 2 run.
- Browser QA used a temporary loopback copy of the same workbench gateway
  against the deployed Railway backend: a 6 MiB upload completed as
  `r_20261025_022345_a3b3`, the saved cloud run loaded, its worksheet generated,
  and an answer could be edited. The report checks also passed for all 158
  fields, sanitized print content and stale-edit clearing. Direct Vercel
  browser inspection is awaiting the user's existing 2FA verification; the
  Vercel API tests used the project's existing private automation bypass.

The trials were sequential, not load or maximum-upload-size tests. The
existing ChatGPT Site and `main` were not modified. Prior Mac run history was
not migrated; these cloud runs are stored independently on Railway's volume.
