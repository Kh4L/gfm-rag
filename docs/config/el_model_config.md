
## Colbert EL Model Configuration

An example of a Colbert EL model configuration file is shown below:

```yaml
_target_: gfmrag.kg_construction.entity_linking_model.ColbertELModel
checkpint_path: tmp/colbertv2.0
root: tmp
doc_index_name: nbits_2
phrase_index_name: nbits_2
```

To use colbertv2.0 model, you need to download the [checkpoint file](https://downloads.cs.stanford.edu/nlp/data/colbert/colbertv2/colbertv2.0.tar.gz) and unzip it into the `checkpint_path`.

An example checkpoint file structure is shown below:

```
tmp/colbertv2.0/
├── artifact.metadata
├── tokenizer.json
├── special_tokens_map.json
├── config.json
├── tokenizer_config.json
├── vocab.txt
└── pytorch_model.bin
```

|      Parameter      |                           Options                            |                                               Note                                               |
| :-----------------: | :----------------------------------------------------------: | :----------------------------------------------------------------------------------------------: |
|     `_target_`      | `gfmrag.kg_construction.entity_linking_model.ColbertELModel` | The class name of [Colbert EL model][gfmrag.kg_construction.entity_linking_model.ColbertELModel] |
|  `checkpoint_path`  |                             None                             |                                 The path to the checkpoint file.                                 |
|       `root`        |                             None                             |                                 The root directory of the model.                                 |
|  `doc_index_name`   |                             None                             |                                 The name of the document index.                                  |
| `phrase_index_name` |                             None                             |                                  The name of the phrase index.                                   |

Please refer to [ColbertELModel][gfmrag.kg_construction.entity_linking_model.ColbertELModel] for details on the other parameters.

## Dense Pre-train Text Embedding Model Configuration

This configuration supports most of the dense pre-train text embedding models of [SentenceTransformer](https://huggingface.co/sentence-transformers). An example of a dense pre-train text embedding model configuration file is shown below:

```yaml
_target_: gfmrag.kg_construction.entity_linking_model.DPRELModel
model_name: BAAI/bge-large-en-v1.5
root: tmp
use_cache: True
normalize: True
query_instruct: null
passage_instruct: null
model_kwargs: null
```


|     Parameter      |                         Options                          |                                                       Note                                                       |
| :----------------: | :------------------------------------------------------: | :--------------------------------------------------------------------------------------------------------------: |
|     `_target_`     | `gfmrag.kg_construction.entity_linking_model.DPRELModel` | The class name of [Dense Pre-train Text Embedding model][gfmrag.kg_construction.entity_linking_model.DPRELModel] |
|    `model_name`    |                           None                           |                              The name of the dense pre-train text embedding model.                               |
|       `root`       |                           None                           |                                         The root directory of the model.                                         |
|    `use_cache`     |                     `True`, `False`                      |                                              Whether to use cache.                                               |
|    `normalize`     |                     `True`, `False`                      |                                       Whether to normalize the embeddings.                                       |
|  `query_instruct`  |                           None                           |                                          The instruction for the query.                                          |
| `passage_instruct` |                           None                           |                                         The instruction for the passage.                                         |
|   `model_kwargs`   |                           None                           |                                         The additional model arguments.                                          |

Please refer to [DPR EL Model][gfmrag.kg_construction.entity_linking_model.DPRELModel] for details on the other parameters.

## Nvidia Embedding Model Configuration

This configuration supports most of the [Nvidia embedding models](https://huggingface.co/nvidia/NV-Embed-v2). An example of a Nvidia embedding model configuration file is shown below:

```yaml
_target_: gfmrag.kg_construction.entity_linking_model.NVEmbedV2ELModel
model_name: nvidia/NV-Embed-v2
root: tmp
use_cache: True
normalize: True
query_instruct: "Instruct: Given a entity, retrieve entities that are semantically equivalent to the given entity\nQuery: "
passage_instruct: null
model_kwargs:
  torch_dtype: bfloat16
```

|     Parameter      |                                                   Options                                                   |                                                   Note                                                   |
| :----------------: | :---------------------------------------------------------------------------------------------------------: | :------------------------------------------------------------------------------------------------------: |
|     `_target_`     |                       `gfmrag.kg_construction.entity_linking_model.NVEmbedV2ELModel`                        | The class name of [Nvidia Embedding model][gfmrag.kg_construction.entity_linking_model.NVEmbedV2ELModel] |
|    `model_name`    |                                            `nvidia/NV-Embed-v2`                                             |                                 The name of the Nvidia embedding model.                                  |
|       `root`       |                                                    None                                                     |                                     The root directory of the model.                                     |
|    `use_cache`     |                                               `True`, `False`                                               |                                          Whether to use cache.                                           |
|    `normalize`     |                                               `True`, `False`                                               |                                   Whether to normalize the embeddings.                                   |
|  `query_instruct`  | `Instruct: Given a entity, retrieve entities that are semantically equivalent to the given entity\nQuery: ` |                                      The instruction for the query.                                      |
| `passage_instruct` |                                                    None                                                     |                                     The instruction for the passage.                                     |
|   `model_kwargs`   |                                                    None                                                     |                                     The additional model arguments.                                      |


Please refer to [NVEmbedV2 EL Model][gfmrag.kg_construction.entity_linking_model.NVEmbedV2ELModel] for details on the other parameters.
