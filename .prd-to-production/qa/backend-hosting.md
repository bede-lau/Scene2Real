# Portable backend hosting QA — 18 October 2026

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
