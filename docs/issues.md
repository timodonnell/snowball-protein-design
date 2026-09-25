# Issue log

Record observed failures separately from anticipated compatibility concerns.

| ID | Stage | Observation | Resolution/status | Attribution |
|---|---|---|---|---|
| I001 | Paper access | Web tool returned 403; local PDF curl returned 429. HTML route exposed only abstract/preview. | Publisher PDF downloaded successfully from CoreWeave; 92-page manuscript and supplement available. | Source access |
| I002 | Resources | US-EAST CoreWeave GPUs occupied; local disk has 47GiB free. | Use RNO2A and dedicated persistent storage. | Infrastructure |
| I003 | CLI | `hf models info --expand sha config safetensors` rejected multiple positional values. | Use supported CLI syntax / Hub metadata API. | Harness setup |
| I004 | Environment capture | Snowball's download finished, then `python -m pip freeze` failed because uv venvs do not include pip. | Captured dependencies with `uv pip freeze --python ...`; corrected setup script. Model files were unaffected. | Harness setup |
| I005 | Snowball server import | Marin vLLM wheel requires Torch 2.13 and TorchAudio 2.11; the resolved audio wheel used CUDA 13.0 while Torch used 13.2. Transformers import aborted before inference. | Attempt to pin TorchAudio 2.13+cu132 failed: no such wheel. Removed TorchAudio for this text-only server. This intentionally leaves vLLM's unused audio dependency unsatisfied. Attempt 3 served a successful text completion. Raw traceback: `artifacts/snowball-serving-precheck-attempt1.txt`. | Serving dependency ABI, not model output |
| I006 | Snowball server startup | Attempt 2 passed model configuration, then FlashInfer's build could not find `ninja`; invoking the venv's Python had not added its bin directory to PATH. | Added each server environment's bin directory to PATH in a shared launch script. | Harness environment activation |

Snowball's custom architecture and shorter context are compatibility checks, not
yet observed inference failures. No Snowball model outputs have been measured yet.
