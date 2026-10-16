# Minerva Coding Agent — Team Setup

Private coding-LLM access for the Untreated IBD group, running entirely inside
MSSM's Minerva HPC cluster. Verified working end-to-end (2026-10-07).

**One harness, two tiers.** Everyone uses [OpenCode](https://opencode.ai); only
the endpoint changes based on data sensitivity.

---

## TL;DR

```bash
# 1. Submit the model server (once per walltime window)
bsub < vllm/vllm-qwen.lsf
bjobs -w                                  # note the EXEC_HOST

# 2. Authenticate ONCE (MFA), hold the channel open
ssh -MNf -o ControlPersist=8h minerva

# 3. Tunnel to the compute node (no MFA prompt)
ssh -N -L 8000:localhost:8000 tastac01@<EXEC_HOST>

# 4. Verify, then use
curl -s http://localhost:8000/v1/models \
  -H "Authorization: Bearer $(cat ~/.vllm_key)" | python3 -m json.tool
export MINERVA_VLLM_KEY=$(cat ~/.vllm_key)
opencode
```

---

## 1. Architecture

| | **Tier 1 — Sensitive** | **Tier 2 — General** |
|---|---|---|
| **Use for** | Patient data, PHI, anything under IRB | Public code, docs, non-sensitive scripts |
| **Endpoint** | Self-hosted vLLM on Minerva GPU nodes | Institution-approved hosted service |
| **Data leaves cluster?** | **No — never** | Approved only |
| **Config file** | `opencode.json` (this repo) | `.opencode/opencode.hosted.json` |

**Rule of thumb:** if you have to think about whether it's sensitive, use Tier 1.

### Request path

```
OpenCode ──HTTP──▶ localhost:8000 ──[SSH tunnel]──▶ login node ──▶ compute node:8000 ──▶ vLLM
 (laptop)              (local socket)              (MFA happened here)     (loopback only)
```

**OpenCode never speaks SSH.** It talks plain HTTP to `localhost:8000`. Port 8000
is vLLM's HTTP port, not an SSH port. MFA is consumed once, by the tunnel — never
by OpenCode.

---

## 2. Modular Deployment System

This system supports multiple deployment environments and GPU resources for optimal resource utilization:

### Environments
1. **Minerva HPC Cluster** - High-performance computing with H100 NVLink, L40S, and B200 GPUs
2. **Minimus Local Instance** - Always-on local vLLM instance with A6000 GPU
3. **Development Environment** - Local testing environment

### GPU Selection Priority
1. **A6000 (Minimus)** - Always available, ideal for daily work
2. **L40S** - High availability, balanced performance
3. **H100 NVLink** - Highest performance, when available
4. **B200** - Reserved for critical workloads

### Model Pairings
| GPU Type | Recommended Models | Use Case |
|----------|-------------------|----------|
| A6000 | Qwen3-Coder-7B-A3B, Qwen3-Coder-14B-A3B | Daily work, light analysis |
| L40S | Qwen3-Coder-14B-A3B, Qwen3-Coder-7B-A3B | General purpose |
| H100 NVLink | Qwen3-Coder-30B-A3B, Qwen3-Coder-14B-A3B | Heavy analysis, code generation |

---

## 3. Prerequisites

- Minerva account with the `acc_untreatedIBD` allocation.
- VPN + F5 for off-campus access (a tunnel alone will **not** connect off-campus).
- OpenCode **v2** installed locally.
- SSH access to `minerva.hpc.mssm.edu`.

### One-time SSH config

```
Host minerva
    HostName minerva.hpc.mssm.edu
    User tastac01
    ControlMaster auto
    ControlPath ~/.ssh/cm-%C
    ControlPersist 8h

Host lg* li*
    User tastac01
    ProxyJump minerva
```

- `%C` keeps the control path under the 104/108-byte Unix socket limit.
- **Always use the alias `minerva`, never the FQDN** — the ControlMaster settings
  live in the `Host minerva` block and will *not* apply to
  `minerva.hpc.mssm.edu`. Using the FQDN is the #1 cause of repeated MFA prompts.
- The `lg* li*` block sets the correct username and jump host for compute nodes,
  so you don't have to type `tastac01@` each time.

---

## 4. Repository layout

```
.
├── README.md
├── opencode.json              # OpenCode v2 config → Current active environment
├── minerva-llm-connect.sh     # Connect to Minerva HPC
├── switch-env.sh              # Switch between environments
├── minerva.json               # Minerva HPC configuration
├── minimus.json               # Minimus local instance configuration
├── dev.json                   # Development environment configuration
└── vllm/
    ├── vllm-qwen.lsf          # LSF job that hosts the model
    ├── logs/                  # job stdout/stderr (gitignored)
    └── README.md              # model-server internals
```

**Never commit:** API keys, `auth.json`, `*.sif`, model weights, logs.

---

## 5. OpenCode Configuration (v2 format)

> **The config format changed between v1 and v2.** This repo targets **v2**.
> Using v1 field names produces "provider appears but no models / 401" errors.

| Setting | **v1** | **v2 (use this)** |
|---|---|---|
| Provider map key | `provider` | **`providers`** |
| Runtime package | `npm` | **`package`** |
| Options map | `options` | **`settings`** |
| Compatible runtime | `@ai-sdk/openai-compatible` | `@opencode/ai/providers/openai-compatible` |

`opencode.json`:
```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "minerva/qwen3-coder-30b",
  "providers": {
    "minerva": {
      "name": "Minerva vLLM",
      "env": ["MINERVA_VLLM_KEY"],
      "package": "@opencode/ai/providers/openai-compatible",
      "settings": {
        "baseURL": "http://localhost:8000/v1"
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

`baseURL` must end in `/v1` and nothing more — no `/chat/completions`, no
duplicated `/v1`.

### Required: attach the credential with `/connect`

**The `env` field alone is not sufficient.** Check with `opencode auth list` —
if it says "No authenticated integrations", prompts will 401 even though the key
is valid. Attach it explicitly:

```
/connect   →  select "minerva"  →  paste contents of ~/.vllm_key
```

Credential precedence: **stored (`/connect`) > env var > `settings.apiKey`**.
A stored credential is required for reliable operation; **each developer runs
`/connect` once per machine** (credentials are local, never in the repo).

Verify:

```bash
opencode auth list                                    # should show minerva
curl -s http://localhost:8000/v1/models \
  -H "Authorization: Bearer $(cat ~/.vllm_key)" | python3 -m json.tool
```

---

## 6. Environment Switching

Use the `switch-env.sh` script to easily switch between different deployment environments:

```bash
# Switch to Minerva HPC with 30B model
./switch-env.sh --environment=minerva --model=qwen3-coder-30b

# Switch to Minimus with 14B model
./switch-env.sh --environment=minimus --model=qwen3-coder-14b --gpu=a6000

# Show help
./switch-env.sh --help
```

---

## 7. Submitting the model server

```bash
bsub < vllm/vllm-qwen.lsf
bjobs -w                     # wait for RUN; copy the EXEC_HOST column
bpeek <JOBID>                # watch for "Application startup complete"
```

**The `EXEC_HOST` changes on every resubmission.** Always re-read it from
`bjobs -w`; a stale hostname produces "Connection refused."

---

## 8. Connecting

### Authenticate once
```bash
ssh -MNf -o ControlPersist=8h minerva     # prompts for password + Azure MFA
ssh -O check minerva                      # "Master running (pid=...)" = good
```

### Open the tunnel
```bash
ssh -N -L 8000:localhost:8000 tastac01@<EXEC_HOST>
```

**Why the compute node directly, not the login node:** vLLM binds to
`127.0.0.1` (loopback) on the compute node. A tunnel that makes the *login node*
dial the compute node reaches the node's *network interface*, which a
loopback-bound server refuses:

```
channel 2: open failed: connect failed: Connection refused
```

❌ Wrong with loopback binding:
```bash
ssh -N -L 8000:<EXEC_HOST>:8000 minerva
```

✅ Correct — lands on the compute node, reaches its own loopback:
```bash
ssh -N -L 8000:localhost:8000 tastac01@<EXEC_HOST>
```

### Verify (from your laptop, tunnel live)
```bash
curl -s http://localhost:8000/v1/models \
  -H "Authorization: Bearer $(cat ~/.vllm_key)" | python3 -m json.tool
```

Expect `"id": "qwen3-coder-30b"` and `"max_model_len": 131072`. This is the exact
path OpenCode uses — if this works, OpenCode will work.

---

## 9. Authentication & access model

Two independent layers:

| Layer | Protects | Mechanism |
|---|---|---|
| SSH to login node | Cluster access | Sinai password **+ Azure MFA** |
| vLLM HTTP endpoint | Model access | **API key** (no MFA) |

A `-L` tunnel forwards **exactly one port** — it does *not* grant shell or
filesystem access. Reaching the endpoint requires: campus network (or VPN+F5) →
MFA-authenticated SSH → the API key. Both locks must open.

- **MFA is per-developer, per-connection.** Each person establishes their own
  tunnel to the same node:8000. No shared credential.
- **`ControlPersist` reuses your MFA session** — keep it finite (8h), and treat
  the control socket (`~/.ssh/cm-*`) as a credential.
- **`127.0.0.1` is node-scoped.** On a shared compute node, the API key is what
  prevents other users on the same node from reaching the endpoint.
- **Off-campus requires VPN + F5 first.** A tunnel alone will not connect.

---

## 10. Tool calling (required for agentic use)

OpenCode is an agentic client — it sends `tool_choice: "auto"`, which vLLM
**rejects** unless tool-call parsing was enabled at launch.

**Required flags in `vllm-qwen.lsf`:**

```
--enable-auto-tool-choice
--tool-call-parser qwen3_xml
```

Symptom if missing:
```
Error: "auto" tool choice requires --enable-auto-tool-choice
and --tool-call-parser to be set
```

**Verify after restart** (this is the definitive test — same request shape
OpenCode sends):

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

---

## 11. Context window: keep server and client in sync

The model natively supports **256K (262144) tokens**; we serve at **128K** for a
comfortable VRAM margin.

`vllm-qwen.lsf`:
```
--max-model-len 131072
```

OpenCode requests up to **32000 output tokens** for custom providers
(`OPENCODE_OUTPUT_TOKEN_MAX = 32000`). If the server window is smaller than
input + 32000, every prompt overflows:

```
Error: This model's maximum context length is 32768 tokens. However, you
requested 32000 output tokens and your prompt contains at least 769 input
tokens ... Please reduce the length of the input prompt or the number of
requested output tokens.
✗ Compaction: the compaction request cannot be reduced further ...
```

**Always keep the two sides matched** in `opencode.json`:

| Field | Value | Must equal |
|---|---|---|
| `limit.context` | `131072` | `--max-model-len` |
| `limit.output` | `32768` | Model's max output |
| `limit.input` | `98304` | `context − output` |

Setting `input` explicitly matters: without it, OpenCode derives usable context
as `context − maxOutputTokens()`, which can collapse to a tiny budget and break
compaction. Declaring it gives long agentic sessions a correct, large budget.

**Sizing reference (H100 80GB):**

| `--max-model-len` | Approx. VRAM | Notes |
|---|---|---|
| 32768 | ~38 GB | Too small — overflow errors |
| **131072** | **~50 GB** | **Current default — recommended** |
| 262144 | ~63 GB | Native max; tighter but viable |

The 32000 output cap is a **ceiling, not a floor** — `min(limit.output, 32000)`.
You can lower it, but raising it requires `OPENCODE_EXPERIMENTAL_OUTPUT_TOKEN_MAX`.
The **server-side window is the reliable lever**, since it works regardless of
client config quirks.

---

## 12. Model ID convention

**The served name is a stable alias; the checkpoint path is not.**

| Layer | Value | Changes when… |
|---|---|---|
| Served name (`--served-model-name`) | `qwen3-coder-30b` | We change the *model* |
| Checkpoint path | `/sc/arion/.../snapshots/<rev>/` | We update weights |
| Provider ID | `minerva` | Almost never |
| OpenCode model ref | `minerva/qwen3-coder-30b` | Almost never |

**Never reference a snapshot hash in `opencode.json` or docs.** Pin the hash in
the job script only. A weight update then touches exactly one file.

---

## 13. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Bus error` during weight load | Truncated shards / weights in home quota | Verify no `.incomplete` files; always set `HF_HOME` to project storage |
| Weights download to `~/.cache` | `HF_HOME` not set | Pass `--env HF_HOME=...` |
| `Engine core initialization failed … {}` | Native crash in engine child | Check stderr + `dmesg -T \| grep Xid`; try `--enforce-eager` |
| Crash mid-`Capturing CUDA graphs` | CUDA-graph capture fault | `--enforce-eager` |
| `Failed to infer device type` | GPU not visible | Add `--nv` to `apptainer` |
| `libnvrtc.so.13: cannot open…` | Broken `cu129` image | Use the `cu130` image |
| `Found ulimit of 20000` | fd limit too low | `ulimit -n 65536` |
| MFA prompt on every ssh | Using FQDN, not alias | Use `ssh minerva`; check `ssh -G minerva \| grep -i control` |
| `(cw@node) Password:` | Wrong username on final hop | Spell out `tastac01@<EXEC_HOST>` |
| `channel 2: open failed … refused` | Login node dialing a loopback server | Tunnel to the compute node, not through the login node |
| `Connection refused` (tunnel) | Stale `EXEC_HOST` | Re-read from `bjobs -w` |
| `Expecting value: line 1 column 1` | `curl -s` hiding an empty-body error | Drop `-s` or add `-v`; test on the compute node first |
| Model missing in OpenCode | v1 config fields | Use `providers`/`package`/`settings` |
| Model listed but prompt 401s | No credential attached | `/connect` → minerva |
| `--enable-auto-tool-choice` error | Tool parsing not enabled | Add the two flags; restart |
| Tool calls absent, text only | Wrong parser | Use `qwen3_xml` (fallback `qwen3_coder`) |
| Context-length / compaction error | Client output request exceeds server window | Match `limit.context` to `--max-model-len`; raise window |

### Isolating failures

Test each layer **separately**, in order:

| Layer | Where | Command |
|---|---|---|
| 1. Server | compute node | `curl -s localhost:8000/v1/models` |
| 2. Tunnel | laptop | `curl -s localhost:8000/v1/models -H "Authorization: Bearer $(cat ~/.vllm_key)"` |
| 3. OpenCode | laptop | `opencode` → `/models` |

**Key diagnostic:** `ss -tlnp | grep 8000` on the **client** shows the *tunnel*
(`users:(("ssh",…))`); on the **server** it shows *vLLM*
(`users:(("vllm",…))`). Don't confuse them.

---

## 14. Data handling & compliance

- **Tier 1 traffic never leaves the cluster.** Weights, prompts, and responses
  stay on Minerva; only your SSH tunnel crosses the network.
- **Do not change `--host` to `0.0.0.0`.** That exposes an endpoint to every node
  on the fabric.
- **DeepSeek is prohibited** by internal policy — do not add it to either tier.
- **Logs** may contain prompt text. `vllm/logs/` is gitignored; don't copy logs
  off-cluster if they touched sensitive data.
- **Weights** live in project storage (`/sc/arion/projects/`), never `/scratch`
  (14-day purge).

---

## 15. Operations

### Walltime & resubmission

The job dies at its `-W` walltime, taking the endpoint with it. **Note: the
current script uses `-W 2:00`, which is too short for team use** — raise it and
confirm the `gpu` queue ceiling:

```bash
bqueues -l gpu | grep -i 'runlimit\\|max'
```

A self-resubmit trap on clean exit keeps the service alive across windows.

### Monitoring

```bash
bjobs -w              # your jobs + exec hosts
bpeek <JOBID>         # live tail
bqueues -u $USER      # queue load
```

### Updating the model

1. Download the new checkpoint to `HF_HOME`.
2. Verify no `.incomplete` files; check shard sizes.
3. Update `MODEL_DIR` in `vllm-qwen.lsf`.
4. Keep the same `--served-model-name` so client config is unchanged.
5. `bkill` the old job; submit the new one; re-read `EXEC_HOST`.

---

## 16. Known limitations

- **V100 nodes cannot serve** — vLLM requires compute capability ≥ 7.5.
- **FP8 is native only on Ada/Hopper/Blackwell.** On A100/A6000 it runs
  weight-only (W8A16). Use AWQ/BF16 for Ampere serving if performance matters.
- **`--enforce-eager` costs throughput.** It's a stability workaround; revisit
  once FP8 is confirmed stable (try `--max-cudagraph-capture-size 64`).
- **One GPU = one server.** No tensor parallelism; 30B-A3B fits on one H100.

---

## 17. Modular Deployment Usage

### Switching Between Environments

Use the `switch-env.sh` script to easily switch between different deployment environments:

```bash
# Switch to Minerva HPC with 30B model
./switch-env.sh --environment=minerva --model=qwen3-coder-30b

# Switch to Minimus with 14B model
./switch-env.sh --environment=minimus --model=qwen3-coder-14b --gpu=a6000

# Switch to Development environment
./switch-env.sh --environment=dev --model=qwen3-coder-14b
```

### Environment-Specific Recommendations

#### For Bioinformatics Team:
- Heavy analysis workloads: Use Minerva HPC with H100 NVLink and Qwen3-Coder-30B-A3B
- General development: Use L40S with Qwen3-Coder-14B-A3B

#### For Biologists:
- Light analysis and rapid prototyping: Use Minimus A6000 with Qwen3-Coder-14B-A3B
- Quick scripting: Use L40S with Qwen3-Coder-7B-A3B

---

## 18. Questions / changes

Open a PR rather than configuring by hand — the point of repo-level config is
that the whole team gets the same behavior from a `git pull`.