# Issue log

Record observed failures separately from anticipated compatibility concerns.

| ID | Stage | Observation | Resolution/status | Attribution |
|---|---|---|---|---|
| I001 | Paper access | Web tool returned 403; local PDF curl returned 429. HTML route exposed only abstract/preview. | Publisher PDF downloaded successfully from CoreWeave; 92-page manuscript and supplement available. | Source access |
| I002 | Resources | US-EAST CoreWeave GPUs occupied; local disk has 47GiB free. | Use RNO2A and dedicated persistent storage. | Infrastructure |
| I003 | CLI | `hf models info --expand sha config safetensors` rejected multiple positional values. | Use supported CLI syntax / Hub metadata API. | Harness setup |

Snowball's custom architecture and shorter context are compatibility checks, not
yet observed inference failures. No Snowball model outputs have been measured yet.
