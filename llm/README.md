# Minerva Coding Agent — Team Guide

A private AI coding assistant for the Untreated IBD group. It runs **entirely
inside Minerva** and is used through [OpenCode](https://opencode.ai). Because
nothing leaves the cluster, it is approved for work involving sensitive patient
data.

**Read only the part you need:**

| You are…                                             | Read                                     |
| ---------------------------------------------------- | ---------------------------------------- |
| **A user** who just wants to code with the assistant | [Part 1](#part-1--using-the-assistant)   |
| **An operator** who starts/maintains the server      | [Part 2](#part-2--operating-the-server)  |
| Looking for a specific setting or error              | [Part 3 — Reference](#part-3--reference) |

---

## ⏳ The one thing everyone gets wrong

**The server takes several minutes to start, and the model appears in OpenCode
even when the server is dead.**

Two consequences:

1. **After a job starts, wait.** vLLM loads ~30 GB of weights from shared
   storage. The network port does **not** open until the log prints
   `Application startup complete`. Connecting too early gives
   `Connection refused` — that is normal, not a bug. Wait and retry.
2. **Seeing the model in OpenCode proves nothing.** OpenCode's model list comes
   from its _config file_, not from the server. Always verify with the `curl`
   check below before assuming the connection is live.

---

# Part 1 — Using the assistant

For everyone. Three steps: set up once, connect daily, code.

## 1.1 One-time setup

### a) Install OpenCode (v2)

Follow the instructions at [opencode.ai](https://opencode.ai). Confirm the
version — this guide targets **v2**:

```bash
opencode --version
```

### b) Get the API key

An operator will place the shared key at `~/.vllm_key` on Minerva. Copy it to
your laptop, or ask the operator for it. It must exist on **your laptop** as
`~/.vllm_key`:

```bash
# Verify it exists and is non-empty:
test -s ~/.vllm_key && echo "key present"
```

### c) Add your SSH config

Append this to `~/.ssh/config` on your laptop:

```
Host minerva
    HostName minerva.hpc.mssm.edu
    User tastac01
    ControlMaster auto
    ControlPath ~/.ssh/cm-%C
    ControlPersist 8h
    ServerAliveInterval 30
    ServerAliveCountMax 3
```

- **Always type `minerva`, never the full `minerva.hpc.mssm.edu`.** The settings
  above live in the `Host minerva` block and will _not_ apply if you use the
  full hostname — that is the #1 cause of being asked for MFA over and over.
- `ControlPersist 8h` keeps your MFA session alive so you authenticate **once**
  per work session, not once per command.

### d) Install the OpenCode config

Copy `opencode.json` from this repo into **either**:

- the project you're working in (recommended — travels with the code), or
- `~/.config/opencode/opencode.json` (applies everywhere)

The file must be named exactly `opencode.json` (or `.opencode/opencode.json`).
**`.opencode.json` is not read by OpenCode.**

### e) Attach the credential (once per machine)

OpenCode needs to be told the key. Do **both** of these:

**1. Config-level (already in `opencode.json`):** the provider reads the key
straight from the file —

```json
"settings": {
  "baseURL": "http://localhost:8000/v1",
  "apiKey": "{file:~/.vllm_key}"
}
```

**2. Belt-and-braces:** inside OpenCode, run

```
/connect   →  select "minerva"  →  paste the contents of ~/.vllm_key
```

Then confirm:

```bash
opencode auth list          # should list "minerva"
```

> **Why both?** OpenCode does _not_ read shell environment variables from a
> `.env` file, and a variable set in your terminal may not reach the OpenCode
> process. `{file:...}` is deterministic (read at request time), and a stored
> `/connect` credential takes precedence over everything. Using both removes
> the entire class of "Unauthorized" surprises.

## 1.2 Daily routine

### Step 1 — Is the server running?

Ask an operator, or check yourself:

```bash
ssh minerva "bjobs -w | grep vllm-qwen"
```

You want a line with **`RUN`**. If it says `PEND`, it's queued. If there's no
line, the server is down — ping an operator.

### Step 2 — Connect (open the tunnel)

**Easiest — use the script** (keep the terminal open while you work):

```bash
./minerva-connect.sh
```

It finds the server automatically, authenticates you (password + MFA), and opens
the tunnel. If auto-detection fails, pass the node name:

```bash
./minerva-connect.sh lg05e17
```

**Or do it by hand** (this is the verified-working sequence — three commands):

```bash
# 1. Authenticate to the login node once. Prompts: Sinai password + Azure MFA.
ssh -MNf -o ControlPersist=8h minerva

# 2. Open a login-node session that forwards port 8000 to your laptop.
ssh -L 8000:localhost:8000 minerva

# 3. NOW, from inside that login-node session, forward onward to the compute
#    node. Prompts: your compute-node password (this is the SECOND password).
ssh -L 8000:localhost:8000 tastac01@<EXEC_HOST>
```

Keep both sessions open. The chain is:

```
laptop:8000  →  login node:8000  →  compute node:8000  →  vLLM
```

> **Why two hops, and why two passwords?** The tunnel has to be authenticated
> where each hop is created. The laptop→login hop uses your Sinai password +
> MFA; the login→node hop is authenticated _by the login node_ and asks for the
> compute-node password. This is expected. A single `ProxyJump` command does
> **not** reproduce it, because ProxyJump connects from your laptop, not from
> the login node — which is why it failed before.

### Step 3 — Verify before opening OpenCode

```bash
curl -s http://localhost:8000/v1/models \
  -H "Authorization: Bearer $(cat ~/.vllm_key)" | head
```

You should see `"id":"qwen3-coder-30b"` and `"max_model_len":131072`.

- **JSON returned** → you're good. Go to Step 4.
- **Nothing / `Expecting value: line 1 column 1`** → the tunnel or server is
  down. Do **not** open OpenCode yet; it will just fail. See
  [Part 3](#part-3--reference).

### Step 4 — Open OpenCode

```bash
opencode
```

Select **Minerva vLLM → Qwen3 Coder 30B** (it's the default) and start typing.

## 1.3 If something goes wrong

| What you see                                                 | What to do                                                                             |
| ------------------------------------------------------------ | -------------------------------------------------------------------------------------- |
| OpenCode shows the model but every prompt fails              | Run the Step 3 curl. If it fails, the tunnel is down — reconnect.                      |
| `Unauthorized` on prompts                                    | Run `/connect` again in OpenCode, and confirm `~/.vllm_key` exists.                    |
| Asked for MFA repeatedly                                     | You used the full hostname. Use `ssh minerva` exactly.                                 |
| `Connection refused` right after starting                    | The server is still loading. Wait a few minutes and retry.                             |
| `channel 3: open failed: connect failed: Connection refused` | The server isn't listening yet, or you're on the wrong node. Confirm with an operator. |
| Anything else                                                | Ping an operator with the exact error text.                                            |

---

# Part 2 — Operating the server

For team members comfortable with Minerva/LSF. Everyone else can skip this.

## 2.1 Start the server

```bash
bsub < vllm/vllm-qwen.lsf
bjobs -w                    # note the EXEC_HOST column once state is RUN
```

## 2.2 Wait for it to actually serve

This is the step that trips people up. A `RUN` job does **not** mean the model is
ready. The port opens only at the end of startup:

```bash
# Watch the log until you see these two lines:
tail -f /sc/arion/projects/untreatedIBD/vllm/logs/<JOBID>.stdout
#   INFO: Application startup complete.
#   INFO: Uvicorn running on http://127.0.0.1:8000
```

Confirm the socket exists **on the compute node**:

```bash
ssh tastac01@<EXEC_HOST> "ss -tlnp | grep 8000"
```

A `RUN` job with no listener means startup is still in progress — or it crashed
(see troubleshooting). Budget **several minutes** per restart; the whole team's
tunnel depends on the node staying up.

## 2.3 GPU sizing — H100 vs L40S

The job must be sized to the GPU it actually lands on. `--max-model-len` drives
KV-cache memory, and the two cards differ a lot:

| GPU      | VRAM  | `--max-model-len` | Extra flags needed                                   |
| -------- | ----- | ----------------- | ---------------------------------------------------- |
| **H100** | 80 GB | `131072` (128K)   | none                                                 |
| **L40S** | 48 GB | `131072` (128K)   | `--kv-cache-dtype fp8 --gpu-memory-utilization 0.92` |
| **L40S** | 48 GB | `65536` (64K)     | none (but update `opencode.json`)                    |

If 128K won't fit on the L40S, vLLM fails at KV-cache allocation with
`No available memory for the cache blocks`, leaving a `RUN` job with no listener.
The fix is FP8 KV cache (halves the cache) or a smaller window.

> **If you reduce `--max-model-len`, you MUST update `opencode.json` to match**
> (`limit.context`), or every prompt overflows. See [Part 3](#part-3--reference).

**Match the resource request to the hardware.** The script currently requests
`h100nvl`; if you intend L40S, request it explicitly. Confirm the exact selector
string for your queue with `bhosts -l` or your cluster docs — a mismatch means
the job can land somewhere you didn't size for.

## 2.4 Walltime & resubmission

> ⚠️ **The script currently uses `-W 2:00` (two hours).** That is a testing
> value. For a team endpoint it means the server dies mid-session and every
> user's tunnel breaks. Raise it to the queue maximum before rollout:

```bash
bqueues -l gpu | grep -i 'runlimit\|max'
```

A self-resubmit trap on clean exit keeps the service alive across windows. When
the job moves, **the `EXEC_HOST` changes** — tell the team to re-run
`./minerva-connect.sh`, which re-detects it.

## 2.5 Updating the model

1. Download the new checkpoint into `HF_HOME`.
2. Verify no `.incomplete` files and check shard sizes.
3. Update `MODEL_DIR` in `vllm-qwen.lsf`.
4. **Keep `--served-model-name qwen3-coder-30b` unchanged** — client config then
   needs no edit.
5. `bkill` the old job, `bsub` the new one, announce the new node.

## 2.6 Monitoring

```bash
bjobs -w                 # jobs + exec hosts
bpeek <JOBID>            # live tail of stdout/stderr
bqueues -u $USER         # queue load
```

---

# Part 3 — Reference

## 3.1 Architecture

|                          | **Tier 1 — Sensitive**                | **Tier 2 — General**                     |
| ------------------------ | ------------------------------------- | ---------------------------------------- |
| **Use for**              | Patient data, PHI, anything under IRB | Public code, docs, non-sensitive scripts |
| **Endpoint**             | Self-hosted vLLM on Minerva           | Institution-approved hosted service      |
| **Data leaves cluster?** | **No — never**                        | Approved only                            |
| **Config file**          | `opencode.json`                       | `.opencode/opencode.hosted.json`         |

If you have to think about whether it's sensitive, use Tier 1.

```
OpenCode ──HTTP──▶ laptop:8000 ══SSH══▶ login:8000 ══SSH══▶ node:8000 ──▶ vLLM
   (your machine)      (hop 1: MFA)   (hop 2: node pw)      (loopback only)
```

**OpenCode never speaks SSH.** It talks plain HTTP to `localhost:8000`. Port
8000 is vLLM's HTTP port, not an SSH port. MFA is consumed by the tunnel, never
by OpenCode.

## 3.2 Repository layout

```
.
├── README.md
├── opencode.json              # OpenCode v2 config → Tier 1 (sensitive)
├── minerva-connect.sh         # one-command tunnel
└── vllm/
    ├── vllm-qwen.lsf          # LSF job that hosts the model
    ├── logs/                  # job stdout/stderr (gitignored)
    └── README.md              # model-server internals
```

**Never commit:** API keys, `auth.json`, `*.sif`, model weights, logs.

## 3.3 OpenCode config (v2 format)

> **The format changed between v1 and v2.** This repo targets **v2**. Using v1
> field names gives "provider appears but no models / 401" errors.

| Setting          | v1         | **v2 (use this)** |
| ---------------- | ---------- | ----------------- |
| Provider map key | `provider` | **`providers`**   |
| Runtime package  | `npm`      | **`package`**     |
| Options map      | `options`  | **`settings`**    |

`opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "minerva/qwen3-coder-30b",
  "providers": {
    "minerva": {
      "name": "Minerva vLLM",
      "package": "@opencode/ai/providers/openai-compatible",
      "settings": {
        "baseURL": "http://localhost:8000/v1",
        "apiKey": "{file:~/.vllm_key}"
      },
      "models": {
        "qwen3-coder-30b": {
          "name": "Qwen3 Coder 30B-A3B (FP8)",
          "limit": {
            "context": 131072,
            "output": 32768,
            "input": 98304
          }
        }
      }
    }
  }
}
```

- `baseURL` must end at `/v1` — no `/chat/completions`, no doubled `/v1`.
- `{file:~/.vllm_key}` reads the key at request time. This is more reliable than
  an environment variable, which the OpenCode process may not inherit.

## 3.4 Credentials

Precedence: **stored (`/connect`) → env var → `settings.apiKey`**.

The robust setup is `{file:...}` in config **plus** a one-time `/connect`.
Because a stored credential wins, a stale one must be replaced (re-run
`/connect`), not left in place.

Check what OpenCode sees:

```bash
opencode auth list          # should list "minerva"
```

## 3.5 Tool calling (required)

OpenCode is an agentic client — it sends `tool_choice: "auto"`, which vLLM
**rejects** unless tool parsing was enabled at launch. Required flags:

```
--enable-auto-tool-choice
--tool-call-parser qwen3_xml
```

Symptom if missing:

```
Error: "auto" tool choice requires --enable-auto-tool-choice
and --tool-call-parser to be set
```

Definitive test (same shape OpenCode sends):

```bash
curl -s http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer $(cat ~/.vllm_key)" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3-coder-30b",
    "messages": [{"role":"user","content":"List the files here using the list_files tool."}],
    "tools": [{"type":"function","function":{"name":"list_files","description":"List files","parameters":{"type":"object","properties":{}}}}],
    "tool_choice": "auto",
    "max_tokens": 128
  }' | python3 -m json.tool
```

The response must contain `"tool_calls"` and `"finish_reason": "tool_calls"`.

## 3.6 Context window — keep both sides in sync

The model natively supports **256K**; we serve **128K** for VRAM margin.

OpenCode requests up to **32000 output tokens** for custom providers. If the
server window is smaller than input + 32000, every prompt overflows:

```
Error: This model's maximum context length is 32768 tokens. However, you
requested 32000 output tokens ...
✗ Compaction: the compaction request cannot be reduced further ...
```

Keep these matched in `opencode.json`:

| Field           | Value    | Must equal         |
| --------------- | -------- | ------------------ |
| `limit.context` | `131072` | `--max-model-len`  |
| `limit.output`  | `32768`  | Model's max output |
| `limit.input`   | `98304`  | `context − output` |

**If you change `--max-model-len`, change `limit.context` (and `input`) to
match.** Setting `input` explicitly matters: without it OpenCode derives a tiny
usable budget and compaction breaks.

## 3.7 Model ID convention

| Layer                               | Value                            | Changes when…         |
| ----------------------------------- | -------------------------------- | --------------------- |
| Served name (`--served-model-name`) | `qwen3-coder-30b`                | We change the _model_ |
| Checkpoint path                     | `/sc/arion/.../snapshots/<rev>/` | We update weights     |
| Provider ID                         | `minerva`                        | Almost never          |
| OpenCode model ref                  | `minerva/qwen3-coder-30b`        | Almost never          |

**Never reference a snapshot hash in `opencode.json` or docs.** Pin it in the
job script only.

## 3.8 Troubleshooting

| Symptom                                    | Cause                                    | Fix                                                                                       |
| ------------------------------------------ | ---------------------------------------- | ----------------------------------------------------------------------------------------- |
| `Bus error` during weight load             | Truncated shards / weights in home quota | Check for `.incomplete`; set `HF_HOME` to project storage                                 |
| Weights download to `~/.cache`             | `HF_HOME` not set                        | Pass `--env HF_HOME=...`                                                                  |
| `Engine core initialization failed … {}`   | Native crash in engine child             | Check stderr + `dmesg -T \| grep Xid`; try `--enforce-eager`                              |
| Crash mid-`Capturing CUDA graphs`          | CUDA-graph capture fault                 | `--enforce-eager`                                                                         |
| `No available memory for the cache blocks` | Context too large for the GPU            | Add `--kv-cache-dtype fp8` + raise `--gpu-memory-utilization`, or lower `--max-model-len` |
| `Failed to infer device type`              | GPU not visible                          | Add `--nv` to `apptainer`                                                                 |
| `libnvrtc.so.13: cannot open…`             | Broken `cu129` image                     | Use the `cu130` image                                                                     |
| `Found ulimit of 20000`                    | fd limit too low                         | `ulimit -n 65536`                                                                         |
| MFA prompt on every ssh                    | Using FQDN, not alias                    | Use `ssh minerva`; check `ssh -G minerva \| grep -i control`                              |
| `(cw@node) Password:`                      | Wrong username on final hop              | Spell out `tastac01@<EXEC_HOST>`                                                          |
| `channel N: open failed … refused`         | Nothing listening at the far node        | Confirm job is `RUN`, on the right node, and past startup                                 |
| `Connection refused` right after submit    | Server still loading                     | Wait for `Application startup complete`                                                   |
| `Expecting value: line 1 column 1`         | `curl` got an empty body                 | Drop `-s` or add `-v`; test on the compute node first                                     |
| Model missing in OpenCode                  | v1 config fields                         | Use `providers`/`package`/`settings`                                                      |
| Model listed but prompt 401s               | No credential attached                   | `/connect` → minerva; check `~/.vllm_key`                                                 |
| `--enable-auto-tool-choice` error          | Tool parsing not enabled                 | Add the two flags; restart                                                                |
| Tool calls absent, text only               | Wrong parser                             | Use `qwen3_xml` (fallback `qwen3_coder`)                                                  |
| Context-length / compaction error          | Client request exceeds server window     | Match `limit.context` to `--max-model-len`                                                |
| `ECONNRESET` on prompts                    | Usually a dead endpoint                  | Run the Step-3 curl; if it fails, it's the tunnel                                         |

### Isolating a failure

Test each layer separately, in order:

| Layer       | Where        | Command                                                                          |
| ----------- | ------------ | -------------------------------------------------------------------------------- |
| 1. Server   | compute node | `curl -s localhost:8000/v1/models`                                               |
| 2. Tunnel   | laptop       | `curl -s localhost:8000/v1/models -H "Authorization: Bearer $(cat ~/.vllm_key)"` |
| 3. OpenCode | laptop       | `opencode` → `/models`                                                           |

**Key diagnostic:** `ss -tlnp | grep 8000` on the **client** shows the _tunnel_
(`ssh`); on the **server** it shows _vLLM_ (`vllm`). Don't confuse them.

## 3.9 Data handling & compliance

- **Tier 1 traffic never leaves the cluster.** Only your SSH tunnel crosses the
  network.
- **Do not change `--host` to `0.0.0.0`.** That exposes the endpoint to the whole
  fabric.
- **DeepSeek is prohibited** by internal policy.
- **Logs** may contain prompt text. `vllm/logs/` is gitignored; don't copy logs
  off-cluster if they touched sensitive data.
- **Weights** live in project storage (`/sc/arion/projects/`), never `/scratch`
  (14-day purge).

## 3.10 Known limitations

- **V100 nodes cannot serve** — vLLM needs compute capability ≥ 7.5.
- **FP8 is native only on Ada/Hopper/Blackwell** (L40S, H100). On A100/A6000 it
  runs weight-only (W8A16) — use AWQ/BF16 there.
- **`--enforce-eager` costs throughput** — a stability workaround; revisit once
  FP8 is confirmed stable.
- **One GPU = one server.** No tensor parallelism; the 30B-A3B fits on one H100
  or one L40S (with FP8 KV cache at 128K).

---

## Questions / changes

Open a PR rather than configuring by hand — the point of repo-level config is
that the whole team gets identical behavior from a `git pull`.
