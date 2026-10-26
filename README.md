# local-bedrock

Call AWS Bedrock's API locally, without an AWS account. [fakecloud](https://github.com/faiscadev/fakecloud) emulates AWS at `localhost:4566` and forwards Bedrock `InvokeModel` requests to an [Ollama](https://ollama.com) container on the same Docker network.

## Architecture

```mermaid
flowchart LR
    subgraph host["Your machine"]
        subgraph venv["Python 3.13 (.venv)"]
            stateless["call_llm.py<br/>(stateless)"]
            memory["call_llm_with_memory.py<br/>(last 5 turns as context)"]
            shared["bedrock.py<br/>create_bedrock_client()<br/>call_bedrock_llm()"]
        end
        subgraph docker["Docker Compose network"]
            fakecloud["fakecloud :4566<br/>emulated bedrock-runtime"]
            ollama[("ollama :11434 (host :11435)<br/>OLLAMA_MODEL (default deepseek-r1:1.5b)<br/>models in volume 'ollama'")]
        end
    end

    stateless --> shared
    memory --> shared
    shared -- "1. InvokeModel (boto3, dummy credentials)<br/>modelId amazon.titan-text-express-v1<br/>Titan body: inputText + textGenerationConfig" --> fakecloud
    fakecloud -- "2. POST http://ollama:11434/api/chat<br/>model = FAKECLOUD_BEDROCK_UPSTREAM_MODEL" --> ollama
    ollama -- "3. chat reply" --> fakecloud
    fakecloud -- "4. Titan response: results[].outputText" --> shared
```

1. A script wraps your question in its `DEFAULT_PROMPT` and calls `call_bedrock_llm()`, which sends a Bedrock `InvokeModel` request with boto3 to `localhost:4566` instead of AWS.
2. fakecloud translates it into an Ollama `/api/chat` request. It ignores the model in `modelId` and uses `FAKECLOUD_BEDROCK_UPSTREAM_MODEL` from `docker-compose.yml`, and reaches the `ollama` container by its service name.
3. Ollama generates the reply with the local model, running on CPU inside Docker.
4. fakecloud wraps the reply in the response format of the requested `modelId` (Titan here), and `call_bedrock_llm()` extracts the text. Real AWS is never contacted.

## Requirements

- Docker with Compose
- Python 3.13

Ollama runs in Docker, so you don't need it installed on your machine.

## Setup

```bash
# 1. Start Ollama and the AWS emulator
docker compose up -d

# 2. Create the virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On first boot the `ollama` container downloads `deepseek-r1:1.5b` (about 1.1 GB) into the `ollama` volume; later boots reuse it. fakecloud waits until the model is ready (the `ollama` healthcheck), so `docker compose up -d` can take a few minutes the first time. Follow it with `docker logs -f ollama`.

## Usage

Both scripts open an interactive loop: type a question at the `>>>` prompt, read the reply, repeat. Type `exit` to quit.

```bash
python call_llm.py               # stateless: each question is sent on its own
python call_llm_with_memory.py   # chat: recent turns are sent as context
```

| Script | Behaviour |
|---|---|
| `call_llm.py` | Wraps each question in `DEFAULT_PROMPT` (asks for one short sentence, max 20 words) and prints the reply. No memory between questions. |
| `call_llm_with_memory.py` | Keeps an in-memory `session_history` and injects it into `DEFAULT_PROMPT` as `User:` / `Assistant:` lines, so the model can refer to earlier turns. Only the last 5 turns are kept; history is lost on exit. |

Each script defines its own `DEFAULT_PROMPT`; edit it there to change the prompt. Everything else is shared in `bedrock.py`: the boto3 client (`create_bedrock_client`), the request/response handling (`call_bedrock_llm`), generation settings in `textGenerationConfig` (`temperature` 0.2, `maxTokenCount` 1000), and the real Bedrock model ID `amazon.titan-text-express-v1` (`DEFAULT_MODEL_ID`). Which Ollama model responds is set by `OLLAMA_MODEL` (see Configuration).

The boto3 client uses `endpoint_url="http://localhost:4566"` and dummy credentials, so the real AWS cloud is never contacted. The request body follows the Amazon Titan text format (`inputText` + `textGenerationConfig`).

## Configuration

The model is set once, by `OLLAMA_MODEL` (default `deepseek-r1:1.5b`). Both services read it: the `ollama` container pulls it on boot if missing, and fakecloud sends requests to it. Override it from your shell or a `.env` file:

```bash
OLLAMA_MODEL=llama3.2:1b docker compose up -d
```

Changing it recreates both containers; `ollama` pulls the new model on boot, and fakecloud waits for it again. Models pulled earlier stay in the volume.

fakecloud forwards Bedrock calls using these variables from `docker-compose.yml`:

| Variable | Value | Purpose |
|---|---|---|
| `FAKECLOUD_BEDROCK_UPSTREAM_URL` | `http://ollama:11434` | Ollama base URL, as seen from the fakecloud container |
| `FAKECLOUD_BEDROCK_UPSTREAM_PROTOCOL` | `ollama` | Upstream API (`/api/chat`) |
| `FAKECLOUD_BEDROCK_UPSTREAM_MODEL` | `${OLLAMA_MODEL}` | Ollama model actually serving requests |

The `ollama` container is published on host port `11435` (not `11434`), so it doesn't clash with an Ollama already running on your machine. Use it for debugging, e.g. `curl localhost:11435/api/tags`.

If `FAKECLOUD_BEDROCK_UPSTREAM_URL` is not set, fakecloud returns a canned `"This is a test response from the emulated model."`.

fakecloud strips everything up to the last `.` in `modelId` (treating it as a Bedrock provider prefix), so `deepseek-r1:1.5b` would reach Ollama as `5b`. This is why the Ollama model is set using `FAKECLOUD_BEDROCK_UPSTREAM_MODEL` instead.

The response format depends on `modelId`: a Titan ID such as `amazon.titan-text-express-v1` returns `results[].outputText`; other IDs return `{"output": "..."}`. `call_bedrock_llm` handles either shape, plus `outputs[].text`.

DeepSeek-R1 reasons before answering, so keep `maxTokenCount` high (1000 in `bedrock.py`). With only 100 tokens, it exhausts before finishing and returns an empty output.

## SBOM

`sbom.cdx.json` is a [CycloneDX](https://cyclonedx.org) 1.6 software bill of materials for the Python dependencies in `requirements.txt`, with versions, licences, package URLs and the dependency graph. It does not cover the `fakecloud` or `ollama` container images.

To regenerate it after changing dependencies (requires [uv](https://docs.astral.sh/uv/)):

```bash
uvx --from cyclonedx-bom cyclonedx-py environment .venv/bin/python \
  --mc-type application --output-reproducible --of JSON -o sbom.cdx.json
```

The venv's own `pip` ends up in the output; remove its entry from `components` and `dependencies` so the SBOM matches `requirements.txt`.

## Troubleshooting

- **Check logs:** `docker logs -f fakecloud` (emulator), `docker logs -f ollama` (model download and inference)
- **`docker compose up -d` hangs on first run:** the `ollama` container is still downloading the model; fakecloud starts once it's done.
- **`dependency failed to start: container ollama is unhealthy`:** the model download failed (network, or an unknown `OLLAMA_MODEL` name). Check `docker logs ollama` and rerun `docker compose up -d`.
- **Canned test response instead of real model output:** `FAKECLOUD_BEDROCK_UPSTREAM_URL` is not set. Recreate the container with `docker compose up -d`.
- **`model '5b' not found`:** `FAKECLOUD_BEDROCK_UPSTREAM_MODEL` is missing (see Configuration).
- **Slow replies:** Docker on macOS can't use the GPU, so the model runs on CPU.
- **Free the disk space used by models:** `docker compose down -v` deletes the `ollama` volume; the model is downloaded again on the next boot.
