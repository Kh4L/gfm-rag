# Deep GraphRAG

## Dependencies

- Python 3.12
- CUDA 12.4

```bash
conda create -n deep_graphrag python=3.12
conda activate deep_graphrag
poetry install
conda install cuda-toolkit -c nvidia/label/cuda-12.4.1
```

### For development
Install pre-commit hooks
```bash
pre-commit install
```

## Workflow

### Stage1: KG Construction

### Stage2: Deep GraphRAG Training

Unsupervised training on the constructed KG.

```bash
python workflow/stage2_kg_pretraining.py
```
