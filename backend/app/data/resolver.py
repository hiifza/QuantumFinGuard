"""
Resolves each dataset to real data if available, otherwise to the
labeled synthetic fallback (if enabled in config) — and always reports
which one actually happened. This function is the single place that
decision gets made, so nothing downstream has to guess.
"""
import logging
from dataclasses import dataclass

import pandas as pd

from app.core.config import settings
from app.data import loaders, synthetic_generator
from app.data.loaders import DatasetNotFoundError

logger = logging.getLogger("quantumfinguard.ingestion")


class NoDataAvailableError(Exception):
    pass


@dataclass
class ResolvedDataset:
    frame: pd.DataFrame
    is_synthetic: bool
    dataset_name: str


def resolve_ieee_cis(n_rows_if_synthetic: int = 5000) -> ResolvedDataset:
    try:
        return ResolvedDataset(loaders.get_ieee_cis_frame(), is_synthetic=False, dataset_name="ieee_cis")
    except DatasetNotFoundError as exc:
        if not settings.ALLOW_SYNTHETIC_DATA_FALLBACK:
            raise NoDataAvailableError(str(exc)) from exc
        logger.warning("IEEE-CIS real data not found — using labeled SYNTHETIC fallback. %s", exc)
        return ResolvedDataset(
            synthetic_generator.generate_ieee_cis_like(n_rows_if_synthetic),
            is_synthetic=True,
            dataset_name="ieee_cis",
        )


def resolve_ibm_credit(n_rows_if_synthetic: int = 5000) -> ResolvedDataset:
    try:
        return ResolvedDataset(loaders.get_ibm_credit_frame(), is_synthetic=False, dataset_name="ibm_credit")
    except DatasetNotFoundError as exc:
        if not settings.ALLOW_SYNTHETIC_DATA_FALLBACK:
            raise NoDataAvailableError(str(exc)) from exc
        logger.warning("IBM Credit Card real data not found — using labeled SYNTHETIC fallback. %s", exc)
        return ResolvedDataset(
            synthetic_generator.generate_ibm_credit_like(n_rows_if_synthetic),
            is_synthetic=True,
            dataset_name="ibm_credit",
        )


def resolve_ethereum(n_addresses_if_synthetic: int = 800) -> ResolvedDataset:
    try:
        return ResolvedDataset(loaders.get_ethereum_frame(), is_synthetic=False, dataset_name="ethereum")
    except DatasetNotFoundError as exc:
        if not settings.ALLOW_SYNTHETIC_DATA_FALLBACK:
            raise NoDataAvailableError(str(exc)) from exc
        logger.warning("Ethereum real data not found — using labeled SYNTHETIC fallback. %s", exc)
        return ResolvedDataset(
            synthetic_generator.generate_ethereum_like(n_addresses_if_synthetic),
            is_synthetic=True,
            dataset_name="ethereum",
        )


def ingestion_status() -> dict:
    availability = loaders.real_data_available()
    return {
        "ieee_cis": {"real_data_available": availability["ieee_cis"]},
        "ibm_credit": {"real_data_available": availability["ibm_credit"]},
        "ethereum": {"real_data_available": availability["ethereum"]},
        "synthetic_fallback_enabled": settings.ALLOW_SYNTHETIC_DATA_FALLBACK,
    }
