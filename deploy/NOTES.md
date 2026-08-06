# LLM Inference Deployment (Kubernetes)

Local Ollama inference was too slow to run the pipeline at a usable pace, so inference
was moved to the university's GPU Kubernetes cluster. This let the agents run full
open-weight models without external API costs or rate limits.

## Setup

| | |
|---|---|
| Namespace | `mas-project` |
| Deployment | `ollama-deployment` (1 replica, `ollama/ollama:latest`) |
| Service | `ollama-service` — ClusterIP, port 11434 |
| GPU | `nvidia.com/gpu: 1` (requests = limits) |
| Model | `qwen2.5-coder:7b` (4.7 GB) |

## Ollama configuration

- `OLLAMA_NUM_PARALLEL=4` — up to 4 concurrent requests, matching the screening agent's
  concurrency
- `OLLAMA_MAX_LOADED_MODELS=1` — one model resident; the 7B model fits comfortably in the
  allocated GPU
- `OLLAMA_KEEP_ALIVE=24h` — keeps the model in VRAM between runs, avoiding a reload delay
  on every pipeline execution

---

## Connecting a local machine to the cluster

The service is ClusterIP, so it is only reachable from inside the cluster. Local
development tunnels to it via port-forwarding.

### 1. Install kubectl

**Linux (Fedora)**

    sudo dnf install -y kubectl
    kubectl version --client

**macOS**

    brew install kubectl

### 2. Get a kubeconfig

Log in to Rancher (`https://rancher.hs-anhalt.de`), open the namespace where the model
runs, and click **Download KubeConfig**. The file downloads as `main.yaml`.

    mkdir -p ~/.kube
    cp ~/Downloads/main.yaml ~/.kube/config
    chmod 600 ~/.kube/config

On macOS you can also copy the config in Rancher and write it directly:

    pbpaste > ~/.kube/config

Repeat this step if you hit `Forbidden` or `unauthenticated` errors — the token has
expired or lacks permissions for the namespace.

### 3. Verify the connection

    kubectl config get-contexts
    kubectl config current-context      # should point to "main"
    kubectl cluster-info
    kubectl get ns

If the context is not `main`:

    kubectl config use-context main
    kubectl config set-context --current --namespace=mas-project

### 4. Find the service

    kubectl get pods -n mas-project
    kubectl get svc -n mas-project

This shows the service name and its target port.

### 5. Open the tunnel

    kubectl port-forward svc/ollama-service 11434:11434 -n mas-project

Leave this terminal open for the whole session — it is the connection tunnel, and the
application reaches the model through it.

### 6. Point the agents at it

    OLLAMA_BASE_URL=http://localhost:11434/v1

This is why the agents connect to `localhost:11434` — it is the local end of the tunnel,
not a local Ollama instance. Inside Docker Compose the value becomes
`http://host.docker.internal:11434/v1`, since `localhost` inside a container refers to the
container itself.

> The kubeconfig contains a live access token and must never be committed.
> `.kube/` and `*kubeconfig*` are gitignored.

---

## Running a model locally instead

If cluster access is unavailable, the pipeline works against a local Ollama instance —
slower, but no cluster required.

**Linux**

    curl -fsSL https://ollama.com/install.sh | sh
    ollama --version

**Windows / macOS** — download the installer from `https://ollama.com/download`.

Then, on any platform:

    ollama serve                        # runs on http://localhost:11434
    ollama pull qwen2.5-coder:7b
    ollama list
    ollama run qwen2.5-coder:7b         # quick sanity check

No configuration change is needed: `OLLAMA_BASE_URL` already defaults to
`http://localhost:11434/v1`.

---

## Configuration reference

All configuration is passed as environment variables through `docker-compose.yml`, read
from the host shell or a local `.env` file. Copy `.env.example` to `.env` and fill in the
values — `.env` is gitignored and must never be committed.

| Variable | Used by | Default when unset | Purpose |
|---|---|---|---|
| `OLLAMA_BASE_URL` | backend | `http://localhost:11434/v1` | OpenAI-compatible endpoint for the Ollama model, used by the search, screening, and extraction agents. In Docker Compose this is set to `http://host.docker.internal:11434/v1` to reach a port-forwarded model running on the host. |
| `BACKEND_URL` | frontend | `http://127.0.0.1:8000` | Where `ui_app.py` sends pipeline requests. In Docker Compose this is `http://backend:8000` — the backend service's name on the compose network. |
| `OPENALEX_EMAIL` | backend | — | Contact email sent with OpenAlex API requests, as the API's usage policy requests. |
| `LANGSMITH_TRACING` | backend | unset (tracing off) | Set to `true` to enable LangSmith tracing of the pipeline. |
| `LANGSMITH_ENDPOINT` | backend | EU instance (set in Compose) | LangSmith API region. Defaults to `https://eu.api.smith.langchain.com`; override in `.env` if the account is on another instance. |
| `LANGSMITH_API_KEY` | backend | unset (tracing off) | LangSmith API key. Tracing is fully optional — with this unset, the pipeline runs identically to how it would without LangSmith installed at all. |
| `LANGSMITH_PROJECT` | backend | LangSmith default project | Project name that traces are grouped under. |

---

## Known limitation

No PersistentVolume is mounted on the Ollama pod, so pulled models live in the pod's
ephemeral filesystem. A restart would require re-pulling the 4.7 GB model. Mounting a PVC
at `/root/.ollama` is the obvious next step.
