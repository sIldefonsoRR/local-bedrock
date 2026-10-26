# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Local AWS Bedrock emulation sandbox. A `fakecloud` container (`ghcr.io/faiscadev/fakecloud`) emulates AWS on `localhost:4566` and forwards Bedrock `invoke_model` calls to an `ollama` container (`ollama/ollama`) in the same Compose project. Two standalone boto3 scripts call the emulated `bedrock-runtime` in an interactive `>>>` loop (`exit` quits): `call_llm.py` sends each question on its own; `call_llm_with_memory.py` keeps the last 5 turns in `session_history` and injects them into the prompt as `User:`/`Assistant:` lines (lost on exit). Each script only holds its own `DEFAULT_PROMPT` and loop; the client setup (`create_bedrock_client`), `call_bedrock_llm`, `textGenerationConfig`, and connection constants live in the shared `bedrock.py`. Git repo, public on GitHub at `sIldefonsoRR/local-bedrock` (branch `main`); no tests, linter, or build step.

## Commands

```bash
docker compose up -d                 # start ollama, then fakecloud on :4566
source .venv/bin/activate            # Python 3.13 venv
pip install -r requirements.txt      # boto3/botocore pinned
python call_llm.py                   # interactive, stateless
python call_llm_with_memory.py       # interactive, last 5 turns as context
docker logs -f fakecloud             # inspect emulator / Ollama forwarding
docker logs -f ollama                # model pull on boot, inference
docker compose down -v               # also deletes the pulled model (volume)
```

`sbom.cdx.json` (CycloneDX 1.6) mirrors `requirements.txt`; regenerate it whenever dependencies change (command in README.md, then drop `pip` from it).

The model comes from compose variable `OLLAMA_MODEL` (default `deepseek-r1:1.5b`), used by both services. The `ollama` container's entrypoint starts `ollama serve`, waits until it answers, pulls the model if `ollama show` fails, then `wait`s on the server; models persist in the `ollama` named volume. Its healthcheck passes only once the model exists (`start_period` 15m for the first pull), and fakecloud `depends_on` it with `service_healthy`. It is published on host port 11435, not 11434, to avoid clashing with a host Ollama. Both images are pinned to a release tag (not `latest`) in their `image:` lines in `docker-compose.yml`, the only place versions are recorded; don't repeat them in docs. Tags drop the release's `v`. To bump one, edit its `image:` line, run `docker compose pull && docker compose up -d --wait`, and check a call through `call_bedrock_llm` still returns `is_reply` `True`. Inside the compose file, shell variables in `command`/`healthcheck` are escaped as `$$`. Both scripts use the Bedrock ID `amazon.titan-text-express-v1` (`DEFAULT_MODEL_ID` in `bedrock.py`); each script's prompt template is its own `DEFAULT_PROMPT` (asks for one sentence, max 20 words).

## How the pieces connect

- boto3 client uses `endpoint_url="http://localhost:4566"`, region `us-east-1`, and dummy credentials (`fake`/`fake`) — real AWS is never contacted.
- fakecloud strips `modelId` up to its last `.` (Bedrock provider prefix), so Ollama names like `deepseek-r1:1.5b` break (`model '5b' not found`). The real Ollama model is set by `FAKECLOUD_BEDROCK_UPSTREAM_MODEL` in `docker-compose.yml` (from `OLLAMA_MODEL`); `modelId` only picks the response shape.
- Request body uses the Amazon Titan text shape (`inputText` + `textGenerationConfig`). Titan model IDs (`amazon.titan-*`) get Titan's `results[].outputText` back; other IDs get `{"output": ...}`. `call_bedrock_llm` handles both, plus `outputs[].text`, and returns `(text, is_reply)`: the reply and `True`, or a fallback string and `False` (a `LENGTH` hint or the raw JSON on no text; an error message on exception). `call_llm_with_memory.py` prints fallbacks but only stores turns with `is_reply` in history. DeepSeek-R1 spends tokens on reasoning, so a low `maxTokenCount` (e.g. 100) yields an empty `output`.
- fakecloud's upstream is set by `FAKECLOUD_BEDROCK_UPSTREAM_URL` (base URL, no path), `_PROTOCOL` (`ollama` → `/api/chat`; the binary also supports OpenAI `/v1/chat/completions` and Anthropic `/v1/messages`), `_MODEL`; other vars it reads: `_MODEL_MAP`, `_KEY`, `_EMBED_MODEL`. It ignores `OLLAMA_HOST`. Without an upstream URL it returns a canned test response. The URL is `http://ollama:11434` (Compose service name).

User-facing strings and comments are in English; keep that convention.
