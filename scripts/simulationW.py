#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simulação simplificada de conflito xApp MRO vs ES em O-RAN Near-RT RIC.

Baseado no setup do artigo:
- 4 gNBs
- 100 UEs
- tempo: 10 min
- passo: 100 ms
- frequência: 2.4 GHz
- limiar RSRP handover/falha: -110 dBm
- TXP default: 30 dBm
- conflito direto: ES solicita 3 dBm, MRO solicita 50 dBm
- métodos: NC, SBD, P-ES, P-MRO, QACM
- repetição: 500 rodadas
- KPIs: eficiência energética, link failures, handovers e ping-pong

Execute:
    python oran_mro_es_simulation.py

Saídas:
    results_oran_mro_es.csv
    boxplot_energy_efficiency.png
    boxplot_link_failures.png
    boxplot_total_handovers.png
"""

import math
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from dataclasses import dataclass
import concurrent.futures

# Este script realiza uma simulação simplificada de um cenário O-RAN
# onde diferentes métodos de mitigação são testados em termos de eficiência
# energética, falhas de link e mobilidade (handover/ping-pong).
#
# A implementação combina cálculo de propagação, mobilidade de UEs,
# seleção de potência de transmissão e processamento paralelo para
# acelerar a execução em máquinas com múltiplos núcleos.


@dataclass
class SimConfig:
    n_gnbs: int = 4
    n_ues: int = 100
    sim_time_s: float = 600.0
    dt_s: float = 0.1
    adjustment_interval_s: float = 1.0

    frequency_mhz: float = 2400.0
    rsrp_threshold_dbm: float = -110.0

    txp_default_dbm: float = 30.0
    txp_es_dbm: float = 3.0
    txp_mro_dbm: float = 50.0

    cio_db: float = 2.0
    hys_db: float = 0.5
    ttt_ms: float = 0.1
    ret_deg: float = 1.5

    area_size_m: float = 1000.0
    noise_floor_dbm: float = -100.0

    # Modelo simples de tráfego
    bandwidth_hz: float = 20e6

    # Potência fixa por gNB para consumo energético aproximado
    static_power_w: float = 20.0
    pa_efficiency: float = 0.35

    # Ping-pong: retorno para célula anterior em até 2s
    pingpong_window_s: float = 2.0

    # QACM busca TXP mínimo que preserve QoS
    qacm_link_failure_target: int = 4
    qacm_candidate_txp_dbm: tuple = (3, 10, 15, 20, 25, 30, 35, 40, 45, 50)


def dbm_to_w(dbm: float) -> float:
    # Converte uma potência em dBm para Watts.
    # A equação é padrão: dBm -> dBW -> W.
    return 10 ** ((dbm - 30.0) / 10.0)


def fspl_db(distance_m: np.ndarray, freq_mhz: float) -> np.ndarray:
    """Free Space Path Loss: d em km, f em MHz."""
    # Não permitimos distância zero para evitar log10(0).
    d_km = np.maximum(distance_m / 1000.0, 1e-3)
    # FSPL em dB usando a fórmula clássica de espaço livre.
    return 32.44 + 20 * np.log10(d_km) + 20 * np.log10(freq_mhz)


def deploy_gnbs(cfg: SimConfig) -> np.ndarray:
    """Posiciona quatro gNBs em uma grade 2x2 dentro da área."""
    # O layout fixo simplifica a análise e mantém a simulação estável.
    return np.array([
        [250.0, 250.0],
        [750.0, 250.0],
        [250.0, 750.0],
        [750.0, 750.0],
    ], dtype=float)


def init_ues(cfg: SimConfig, rng: np.random.Generator):
    # Gera posições iniciais dos UEs de forma uniforme na área.
    pos = rng.uniform(0, cfg.area_size_m, size=(cfg.n_ues, 2))

    # Distribuição de mobilidade conforme parâmetro do experimento.
    # A ideia é representar três perfis de usuário com velocidades diferentes.
    classes = rng.choice(["walking", "cycling", "driving"], size=cfg.n_ues, p=[0.35, 0.30, 0.35])

    speeds = np.zeros(cfg.n_ues)
    for i, c in enumerate(classes):
        # A velocidade depende da classe de mobilidade.
        if c == "walking":
            speeds[i] = rng.uniform(0.0, 1.0)
        elif c == "cycling":
            speeds[i] = rng.uniform(2.0, 5.0)
        else:
            speeds[i] = rng.uniform(0.0, 5.0)

    # Direção aleatória para cada UE.
    angles = rng.uniform(0, 2 * np.pi, cfg.n_ues)
    vel = np.column_stack([speeds * np.cos(angles), speeds * np.sin(angles)])

    # Cada UE recebe um tipo de serviço para modelar diferentes demandas.
    services = rng.choice(["eMBB", "URLLC", "mMTC"], size=cfg.n_ues, p=[0.40, 0.30, 0.30])
    return pos, vel, services


def move_ues(pos, vel, cfg: SimConfig):
    # Atualiza posições dos UEs a cada passo de tempo.
    pos += vel * cfg.dt_s

    # Quando o UE atinge a borda, ele reflete como em uma parede.
    for axis in [0, 1]:
        low = pos[:, axis] < 0
        high = pos[:, axis] > cfg.area_size_m

        pos[low, axis] = -pos[low, axis]
        vel[low, axis] *= -1

        pos[high, axis] = 2 * cfg.area_size_m - pos[high, axis]
        vel[high, axis] *= -1

    return pos, vel


def compute_rsrp(pos, gnbs, txp_dbm, cfg: SimConfig, rng: np.random.Generator):
    # Distância entre UEs e gNBs.
    d = np.linalg.norm(pos[:, None, :] - gnbs[None, :, :], axis=2)

    # Sombreamento log-normal simulado com ruído normal.
    shadowing = rng.normal(0.0, 4.0, size=d.shape)
    antenna_gain_db = 2.0
    cable_loss_db = 2.0

    # Cálculo simplificado do RSRP em dBm para cada par UE-gNB.
    return txp_dbm + antenna_gain_db - cable_loss_db - fspl_db(d, cfg.frequency_mhz) + shadowing


def estimate_bits(rsrp_serving_dbm, services, cfg: SimConfig):
    # Estima a taxa de bits disponível para cada UE a partir do RSRP.
    # Aqui usamos SNR aproximado e uma função logarítmica de capacidade.
    snr_db = rsrp_serving_dbm - cfg.noise_floor_dbm
    snr_linear = np.maximum(10 ** (snr_db / 10.0), 1e-9)
    spectral_eff = np.log2(1 + snr_linear)

    # Diferentes serviços exigem diferentes parcelas de capacidade.
    service_weight = np.ones(len(services))
    service_weight[services == "eMBB"] = 1.0
    service_weight[services == "URLLC"] = 0.55
    service_weight[services == "mMTC"] = 0.15

    bits = cfg.bandwidth_hz * spectral_eff * service_weight * cfg.dt_s
    return float(np.sum(bits))


def select_txp(method: str, cfg: SimConfig, rng: np.random.Generator):
    # Seleciona a potência de transmissão de acordo com o método de mitigação.
    if method == "NC":
        # NC: escolhe entre ES e MRO aleatoriamente, simulando conflito.
        return cfg.txp_mro_dbm if rng.random() < 0.5 else cfg.txp_es_dbm
    if method == "SBD":
        # SBD: usa potência padrão sem priorizar nenhum xApp.
        return cfg.txp_default_dbm
    if method == "P-ES":
        # Prioriza o ES (potência baixa).
        return cfg.txp_es_dbm
    if method == "P-MRO":
        # Prioriza o MRO (potência alta).
        return cfg.txp_mro_dbm
    raise ValueError(f"Método desconhecido: {method}")


def qacm_select_txp(cfg: SimConfig, pos, gnbs, rng: np.random.Generator):
    """
    Aproximação QACM:
    escolhe a menor TXP candidata que mantém falhas estimadas abaixo do limiar.
    Isso representa balancear energia e robustez.
    """
    # Avalia cada TXP possível e aceita a primeira que mantém poucas falhas.
    for txp in cfg.qacm_candidate_txp_dbm:
        rsrp = compute_rsrp(pos, gnbs, txp, cfg, rng)
        best = np.max(rsrp, axis=1)
        failures = int(np.sum(best < cfg.rsrp_threshold_dbm))
        if failures <= cfg.qacm_link_failure_target:
            return float(txp)
    # Se nenhuma TXP reduz suficientemente as falhas, usa a potência máxima do MRO.
    return float(cfg.txp_mro_dbm)


def run_once(method: str, seed: int, cfg: SimConfig):
    # Executa uma única simulação completa para um método de mitigação.
    # Retorna métricas acumuladas ao longo de todo o tempo de simulação.
    rng = np.random.default_rng(seed)
    gnbs = deploy_gnbs(cfg)
    pos, vel, services = init_ues(cfg, rng)

    # Define a célula servidora inicial para cada UE usando potência padrão.
    rsrp0 = compute_rsrp(pos, gnbs, cfg.txp_default_dbm, cfg, rng)
    serving = np.argmax(rsrp0, axis=1)
    previous_serving = serving.copy()
    last_ho_time = np.full(cfg.n_ues, -9999.0)

    total_bits = 0.0
    total_energy_j = 0.0
    link_failures = 0
    total_handovers = 0
    pingpong = 0

    current_txp = cfg.txp_default_dbm
    steps = int(cfg.sim_time_s / cfg.dt_s)
    adjust_steps = max(1, int(cfg.adjustment_interval_s / cfg.dt_s))

    for step in range(steps):
        t = step * cfg.dt_s

        # A cada intervalo de ajuste, escolhe a TXP segundo o método.
        if step % adjust_steps == 0:
            if method == "QACM":
                current_txp = qacm_select_txp(cfg, pos, gnbs, rng)
            else:
                current_txp = select_txp(method, cfg, rng)

        # Move os UEs e recalcula os sinais recebidos.
        pos, vel = move_ues(pos, vel, cfg)
        rsrp = compute_rsrp(pos, gnbs, current_txp, cfg, rng)

        best_cell = np.argmax(rsrp, axis=1)
        best_rsrp = rsrp[np.arange(cfg.n_ues), best_cell]
        serving_rsrp = rsrp[np.arange(cfg.n_ues), serving]

        # Conta falhas de link se o sinal servindo está abaixo do threshold.
        failed = serving_rsrp < cfg.rsrp_threshold_dbm
        link_failures += int(np.sum(failed))

        # Define se há handover com base em hysteresis + CIO.
        ho_condition = (best_cell != serving) & (best_rsrp > serving_rsrp + cfg.hys_db + cfg.cio_db)
        ho_indices = np.where(ho_condition)[0]

        for ue in ho_indices:
            # Detecta ping-pong quando o UE volta rapidamente para a célula anterior.
            if best_cell[ue] == previous_serving[ue] and (t - last_ho_time[ue]) <= cfg.pingpong_window_s:
                pingpong += 1
            previous_serving[ue] = serving[ue]
            serving[ue] = best_cell[ue]
            last_ho_time[ue] = t

        total_handovers += len(ho_indices)

        # Calcula os bits entregues durante o passo atual.
        serving_rsrp_after = rsrp[np.arange(cfg.n_ues), serving]
        total_bits += estimate_bits(serving_rsrp_after, services, cfg)

        # Converte potência de TXP para energia consumida pelos gNBs.
        tx_power_w = dbm_to_w(current_txp)
        total_power_w = cfg.n_gnbs * (cfg.static_power_w + tx_power_w / cfg.pa_efficiency)
        total_energy_j += total_power_w * cfg.dt_s

    return {
        "method": method,
        "seed": seed,
        "energy_efficiency_gb_per_j": (total_bits / 1e9) / max(total_energy_j, 1e-9),
        "link_failures": link_failures,
        "total_handovers": total_handovers,
        "pingpong_handovers": pingpong,
    }


def run_rep(rep: int, methods, base_seed: int, cfg: SimConfig):
    # Executa todas as simulações para uma única repetição.
    rows = []
    for m in methods:
        rows.append(run_once(m, base_seed + rep * 100 + methods.index(m), cfg))
    return rows


def run_experiment(repetitions=500, base_seed=42):
    # Controla a execução de múltiplas repetições e agrega os resultados.
    cfg = SimConfig()
    methods = ["NC", "SBD", "P-ES", "P-MRO", "QACM"]
    rows = []

    workers = os.cpu_count() or 1
    print(f"Iniciando experimento com {workers} workers (processos).")

    # Usa ProcessPoolExecutor para paralelizar as repetições em diferentes processos.
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(run_rep, rep, methods, base_seed, cfg) for rep in range(repetitions)]

        for completed, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            rows.extend(future.result())
            if completed % 10 == 0 or completed == repetitions:
                print(f"Progresso: {completed}/{repetitions} repetições completas")

    # Salva resultados em CSV para análise posterior.
    df = pd.DataFrame(rows)
    df.to_csv("results_oran_mro_es.csv", index=False)
    return df


def make_boxplot(df, metric, ylabel, filename):
    # Gera um gráfico de caixa para comparar os métodos em uma métrica.
    methods = ["NC", "SBD", "P-ES", "P-MRO", "QACM"]
    data = [df[df["method"] == m][metric].values for m in methods]

    plt.figure(figsize=(8, 4.8))
    plt.boxplot(data, tick_labels=methods, showfliers=True)
    plt.xlabel("Mitigation Method")
    plt.ylabel(ylabel)
    plt.tight_layout()
    plt.savefig(filename, dpi=200)
    plt.close()


def main():
    # Ponto de entrada do script: executa o experimento e mostra resultados.
    df = run_experiment(repetitions=500)

    print("\nResumo por método:")
    print(df.groupby("method")[[
        "energy_efficiency_gb_per_j",
        "link_failures",
        "total_handovers",
        "pingpong_handovers"
    ]].agg(["mean", "median", "std"]).round(4))

    # Gera gráficos para diferentes KPIs.
    make_boxplot(df, "energy_efficiency_gb_per_j", "Energy Efficiency (Gb/J)", "boxplot_energy_efficiency.png")
    make_boxplot(df, "link_failures", "Link Failures", "boxplot_link_failures.png")
    make_boxplot(df, "total_handovers", "Total Handovers", "boxplot_total_handovers.png")

    print("\nArquivos gerados:")
    print("- results_oran_mro_es.csv")
    print("- boxplot_energy_efficiency.png")
    print("- boxplot_link_failures.png")
    print("- boxplot_total_handovers.png")


if __name__ == "__main__":
    main()
