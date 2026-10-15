# Small Advanced examples

Requests contain no gold labels or reference passages. Source: the MIT-labelled
[OSTswiss/MNLIoverSwissVotingBooklets v1.1 dataset](https://huggingface.co/datasets/OSTswiss/MNLIoverSwissVotingBooklets),
zero-based rows 106 and 728, dataset SHA-256
`87ee4afd9c0ee8861106c50f05884481402ca668aecf927df68fc52d915b02fd`.
Claims, vote names and official booklet URLs retain upstream attribution/terms;
no PDF is redistributed. Gold is source-recorded, not newly human-adjudicated.

| Request | Dataset gold | Actual 14 October 70B Docker result |
|---|---|---|
| `advanced-entailment.json` | 0, entailment | Valid entailment, grounded PDF evidence, exit 0 |
| `advanced-neutral.json` | 1, neutral | Raw neutral; rejected `invalid_vote_status`; app exit 1, root make exit 2 |

Keep `data/request.json` as the uncomplicated Beginner smoke. From repository
root or `track_2a`, after loading credentials as described in `docs/RUNNING.md`:

```sh
make run
REQUEST_FILE=/app/data/examples/advanced-entailment.json make run
REQUEST_FILE=/app/data/examples/advanced-neutral.json make run
```

Advanced mode downloads the specified PDF and, on first use, SentenceSwissBERT
into the Docker cache. It requires network access and an authorised endpoint.
Judge-supplied PDFs may instead be mounted under `/app/data`; relative PDF paths
resolve beside the request JSON. Change `REQUEST_FILE`, never application code.

Successful output has exactly `id`, integer `label`, `label_name`, `evidence`
and `metrics`. Evidence entries contain `page` and `text`; metrics contain
`input_tokens`, `output_tokens` and `inference_time_ms`. A valid neutral result
has label 1 and an empty evidence list. The Neutral example currently demonstrates
a failure, not an accepted neutral output. Do not hide its non-zero exit code.
