import logging
import math
import os
from itertools import islice

import hydra
import torch
from hydra.core.hydra_config import HydraConfig
from hydra.utils import get_class
from omegaconf import DictConfig, OmegaConf
from torch import distributed as dist
from torch import nn
from torch.nn import functional as F  # noqa:N812
from torch.utils import data as torch_data
from torch_geometric.data import Data
from tqdm import tqdm

from deep_graphrag import utils
from deep_graphrag.datasets import KGDataset
from deep_graphrag.models import RelUltra
from deep_graphrag.ultra import tasks

# A logger for this file
logger = logging.getLogger(__name__)

separator = ">" * 30
line = "-" * 30


def train_and_validate(
    cfg: DictConfig,
    output_dir: str,
    model: nn.Module,
    kg_data: Data,
    device: torch.device,
    filtered_data: Data | None = None,
    batch_per_epoch: int | None = None,
) -> None:
    if cfg.train.num_epoch == 0:
        return

    world_size = utils.get_world_size()
    rank = utils.get_rank()

    train_triplets = torch.cat(
        [kg_data.target_edge_index, kg_data.target_edge_type.unsqueeze(0)]
    ).t()
    sampler = torch_data.DistributedSampler(train_triplets, world_size, rank)
    train_loader = torch_data.DataLoader(
        train_triplets, cfg.train.batch_size, sampler=sampler
    )

    batch_per_epoch = batch_per_epoch or len(train_loader)

    optimizer = get_class(cfg.optimizer["_target_"])(
        model.parameters(),
        **{k: v for k, v in cfg.optimizer.items() if k != "_target_"},
    )

    num_params = sum(p.numel() for p in model.parameters())
    logger.warning(line)
    logger.warning(f"Number of parameters: {num_params}")

    if world_size > 1:
        parallel_model = nn.parallel.DistributedDataParallel(model, device_ids=[device])
    else:
        parallel_model = model

    step = math.ceil(cfg.train.num_epoch / 10)
    best_result = float("-inf")
    best_epoch = -1

    batch_id = 0
    for i in range(0, cfg.train.num_epoch, step):
        parallel_model.train()
        for epoch in range(i, min(cfg.train.num_epoch, i + step)):
            if utils.get_rank() == 0:
                logger.warning(separator)
                logger.warning("Epoch %d begin" % epoch)

            losses = []
            sampler.set_epoch(epoch)
            for batch in tqdm(
                islice(train_loader, batch_per_epoch),
                desc=f"Training Batches: {epoch}",
                total=batch_per_epoch,
            ):
                batch = tasks.negative_sampling(
                    kg_data,
                    batch,
                    cfg.task.num_negative,
                    strict=cfg.task.strict_negative,
                )
                pred = parallel_model(kg_data, batch)
                target = torch.zeros_like(pred)
                target[:, 0] = 1
                loss = F.binary_cross_entropy_with_logits(
                    pred, target, reduction="none"
                )
                neg_weight = torch.ones_like(pred)
                if cfg.task.adversarial_temperature > 0:
                    with torch.no_grad():
                        neg_weight[:, 1:] = F.softmax(
                            pred[:, 1:] / cfg.task.adversarial_temperature, dim=-1
                        )
                else:
                    neg_weight[:, 1:] = 1 / cfg.task.num_negative
                loss = (loss * neg_weight).sum(dim=-1) / neg_weight.sum(dim=-1)
                loss = loss.mean()

                loss.backward()
                optimizer.step()
                optimizer.zero_grad()

                if utils.get_rank() == 0 and batch_id % cfg.train.log_interval == 0:
                    logger.warning(separator)
                    logger.warning(f"binary cross entropy: {loss:g}")
                losses.append(loss.item())
                batch_id += 1

            if utils.get_rank() == 0:
                avg_loss = sum(losses) / len(losses)
                logger.warning(separator)
                logger.warning("Epoch %d end" % epoch)
                logger.warning(line)
                logger.warning(f"average binary cross entropy: {avg_loss:g}")

        epoch = min(cfg.train.num_epoch, i + step)
        if rank == 0:
            logger.warning("Save checkpoint to model_epoch_%d.pth" % epoch)
            state = {"model": model.state_dict(), "optimizer": optimizer.state_dict()}
            torch.save(state, os.path.join(output_dir, "model_epoch_%d.pth" % epoch))
        utils.synchronize()

        if rank == 0:
            logger.warning(separator)
            logger.warning("Evaluate on valid")
        result = test(cfg, model, kg_data, filtered_data=filtered_data, device=device)
        if result > best_result:
            best_result = result
            best_epoch = epoch

    if rank == 0:
        logger.warning("Load checkpoint from model_epoch_%d.pth" % best_epoch)
    state = torch.load(
        os.path.join(output_dir, "model_epoch_%d.pth" % best_epoch), map_location=device
    )
    model.load_state_dict(state["model"])
    utils.synchronize()


@torch.no_grad()
def test(
    cfg: DictConfig,
    model: nn.Module,
    test_data: Data,
    device: torch.device,
    filtered_data: Data | None = None,
    return_metrics: bool = False,
) -> float | dict:
    world_size = utils.get_world_size()
    rank = utils.get_rank()

    test_triplets = torch.cat(
        [test_data.target_edge_index, test_data.target_edge_type.unsqueeze(0)]
    ).t()
    sampler = torch_data.DistributedSampler(test_triplets, world_size, rank)
    test_loader = torch_data.DataLoader(
        test_triplets, cfg.train.batch_size, sampler=sampler
    )

    model.eval()
    rankings = []
    num_negatives = []
    tail_rankings, num_tail_negs = (
        [],
        [],
    )  # for explicit tail-only evaluation needed for 5 datasets
    for batch in tqdm(test_loader):
        t_batch, h_batch = tasks.all_negative(test_data, batch)
        t_pred = model(test_data, t_batch)
        h_pred = model(test_data, h_batch)

        if filtered_data is None:
            t_mask, h_mask = tasks.strict_negative_mask(test_data, batch)
        else:
            t_mask, h_mask = tasks.strict_negative_mask(filtered_data, batch)
        pos_h_index, pos_t_index, pos_r_index = batch.t()
        t_ranking = tasks.compute_ranking(t_pred, pos_t_index, t_mask)
        h_ranking = tasks.compute_ranking(h_pred, pos_h_index, h_mask)
        num_t_negative = t_mask.sum(dim=-1)
        num_h_negative = h_mask.sum(dim=-1)

        rankings += [t_ranking, h_ranking]
        num_negatives += [num_t_negative, num_h_negative]

        tail_rankings += [t_ranking]
        num_tail_negs += [num_t_negative]

    ranking = torch.cat(rankings)
    num_negative = torch.cat(num_negatives)
    all_size = torch.zeros(world_size, dtype=torch.long, device=device)
    all_size[rank] = len(ranking)

    # ugly repetitive code for tail-only ranks processing
    tail_ranking = torch.cat(tail_rankings)
    num_tail_neg = torch.cat(num_tail_negs)
    all_size_t = torch.zeros(world_size, dtype=torch.long, device=device)
    all_size_t[rank] = len(tail_ranking)
    if world_size > 1:
        dist.all_reduce(all_size, op=dist.ReduceOp.SUM)
        dist.all_reduce(all_size_t, op=dist.ReduceOp.SUM)

    # obtaining all ranks
    cum_size = all_size.cumsum(0)
    all_ranking = torch.zeros(all_size.sum(), dtype=torch.long, device=device)
    all_ranking[cum_size[rank] - all_size[rank] : cum_size[rank]] = ranking
    all_num_negative = torch.zeros(all_size.sum(), dtype=torch.long, device=device)
    all_num_negative[cum_size[rank] - all_size[rank] : cum_size[rank]] = num_negative

    # the same for tails-only ranks
    cum_size_t = all_size_t.cumsum(0)
    all_ranking_t = torch.zeros(all_size_t.sum(), dtype=torch.long, device=device)
    all_ranking_t[cum_size_t[rank] - all_size_t[rank] : cum_size_t[rank]] = tail_ranking
    all_num_negative_t = torch.zeros(all_size_t.sum(), dtype=torch.long, device=device)
    all_num_negative_t[cum_size_t[rank] - all_size_t[rank] : cum_size_t[rank]] = (
        num_tail_neg
    )
    if world_size > 1:
        dist.all_reduce(all_ranking, op=dist.ReduceOp.SUM)
        dist.all_reduce(all_num_negative, op=dist.ReduceOp.SUM)
        dist.all_reduce(all_ranking_t, op=dist.ReduceOp.SUM)
        dist.all_reduce(all_num_negative_t, op=dist.ReduceOp.SUM)

    metrics = {}
    if rank == 0:
        for metric in cfg.task.metric:
            if "-tail" in metric:
                _metric_name, direction = metric.split("-")
                if direction != "tail":
                    raise ValueError("Only tail metric is supported in this mode")
                _ranking = all_ranking_t
                _num_neg = all_num_negative_t
            else:
                _ranking = all_ranking
                _num_neg = all_num_negative
                _metric_name = metric

            if _metric_name == "mr":
                score = _ranking.float().mean()
            elif _metric_name == "mrr":
                score = (1 / _ranking.float()).mean()
            elif _metric_name.startswith("hits@"):
                values = _metric_name[5:].split("_")
                threshold = int(values[0])
                if len(values) > 1:
                    num_sample = int(values[1])
                    # unbiased estimation
                    fp_rate = (_ranking - 1).float() / _num_neg
                    score = 0
                    for i in range(threshold):
                        # choose i false positive from num_sample - 1 negatives
                        num_comb = (
                            math.factorial(num_sample - 1)
                            / math.factorial(i)
                            / math.factorial(num_sample - i - 1)
                        )
                        score += (
                            num_comb
                            * (fp_rate**i)
                            * ((1 - fp_rate) ** (num_sample - i - 1))
                        )
                    score = score.mean()
                else:
                    score = (_ranking <= threshold).float().mean()
            logger.warning(f"{metric}: {score:g}")
            metrics[metric] = score
    mrr = (1 / all_ranking.float()).mean()

    return mrr if not return_metrics else metrics


@hydra.main(config_path="config", config_name="stage2_kg_pretrain", version_base=None)
def main(cfg: DictConfig) -> None:
    output_dir = HydraConfig.get().runtime.output_dir
    utils.init_distributed_mode()
    torch.manual_seed(cfg.seed + utils.get_rank())
    if utils.get_rank() == 0:
        logger.info(f"Config:\n {OmegaConf.to_yaml(cfg)}")
        logger.info(f"Current working directory: {os.getcwd()}")
        logger.info(f"Output directory: {output_dir}")

    kg_data = KGDataset(**cfg.dataset)[0]
    device = utils.get_device()
    kg_data = kg_data.to(device)
    rel_emb = kg_data.rel_emb

    model = RelUltra(cfg.model.entity_model_cfg, rel_emb_dim=rel_emb.shape[-1])

    if "checkpoint" in cfg and cfg.checkpoint is not None:
        state = torch.load(cfg.checkpoint, map_location="cpu")
        model.load_state_dict(state["model"])

    model = model.to(device)

    val_filtered_data = Data(
        edge_index=kg_data.target_edge_index,
        edge_type=kg_data.target_edge_type,
        num_nodes=kg_data.num_nodes,
    )

    val_filtered_data = val_filtered_data.to(device)

    train_and_validate(
        cfg,
        output_dir,
        model,
        kg_data,
        filtered_data=val_filtered_data,
        device=device,
        batch_per_epoch=cfg.train.batch_per_epoch,
    )

    if utils.get_rank() == 0:
        logger.warning(separator)
        logger.warning("Evaluate on valid")
    test(cfg, model, kg_data, filtered_data=val_filtered_data, device=device)


if __name__ == "__main__":
    main()
