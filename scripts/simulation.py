# ============================================================
# SIMULAÇÃO DE GERENCIAMENTO DE MOBILIDADE EM REDES O-RAN
# ============================================================
# Este código implementa uma simulação de rede celular 5G/O-RAN com foco
# no gerenciamento de mobilidade (Mobility Management) e balanceamento de
# carga (Load Balancing). Inclui modelagem de estações base, usuários móveis,
# propagação de sinal, handovers, eventos de ping-pong, RLF (Radio Link Failure)
# e controle via xApps RIC (RAN Intelligent Controller).
#
# Principais componentes:
# - 19 estações base em grid hexagonal (layout típico de rede celular)
# - 380 usuários (UE) com diferentes perfis de tráfego
# - Modelo de propagação 3GPP UMa (Urban Macro)
# - Lógica de handover A3 (Event A3 do 3GPP)
# - xApps RIC para MRO (Mobility Robustness Optimization) e MLB (Load Balancing)

import os
import argparse
import concurrent.futures
import csv
from datetime import datetime
import numpy as np
import matplotlib.pyplot as plt
from dataclasses import dataclass, field
from collections import deque, defaultdict

# ============================================================
# CONFIGURAÇÃO GERAL DA SIMULAÇÃO
# ============================================================
# Parâmetros globais que definem a estrutura da simulação:
# - N_BS: Número de estações base (19 em grid hexagonal)
# - USERS_PER_BS: Usuários por estação base
# - INTER_SITE_DISTANCE: Distância entre estações base (ISD)
# - SIM_TIME: Tempo total de simulação em segundos
# - DT: Passo de tempo (time step) da simulação

np.random.seed(42)  # Semente para reprodutibilidade dos resultados

N_BS = 19  # 19 estações base em layout hexagonal
USERS_PER_BS = 20  # 20 usuários por BS = 380 usuários total
N_USERS = N_BS * USERS_PER_BS  # Total de usuários na simulação

INTER_SITE_DISTANCE = 600.0  # Distância entre sites (metros)
SIMULATION_AREA_MARGIN_FACTOR = 1.5  # Margem do polígono em múltiplos da distância entre sites

SIM_TIME = 1000.0  # Tempo total de simulação: 1000 segundos
DT = 0.05  # Passo de tempo: 50ms (cada step = 50ms)
STEPS = int(SIM_TIME / DT)  # Total de passos de tempo (20000 steps)

# ============================================================
# PARÂMETROS DAS ESTAÇÕES BASE (Base Stations - BS)
# ============================================================
# Define as características físicas e de transmissão das BSs:
# - Potência de transmissão (tx_power_dbm): 28 dBm = ~630 mW
# - Ganho de antena: 2 dB (antenas diretivas)
# - Altura da torre: 10 metros
# - Perda no cabo: 2 dB (conectores e cabo RF)

BS_TX_POWER_DBM = 28.0  # Potência de transmissão em dBm
BS_ANTENNA_GAIN_DB = 2.0  # Ganho da antena da BS em dB
BS_HEIGHT_M = 10.0  # Altura da torre da BS em metros
BS_CABLE_LOSS_DB = 2.0  # Perda no cabo de RF em dB

CENTER_FREQ_GHZ = 2.1  # Frequência central em GHz (banda 2.1 GHz)
BANDWIDTH_HZ = 20e6  # Largura de banda do canal: 20 MHz
SUBCARRIER_COUNT = 12  # Número de subportadoras (para referência)
SUBCARRIER_SPACING_HZ = 15e3  # Espaçamento entre subportadoras: 15 kHz

# Parâmetros de handover (A3 event - 3GPP)
# - CIO: Cell Individual Offset - ajuste de offset para balanceamento
# - TTT: Time To Trigger - tempo mínimo para confirmar handover
# - Hysteresis: margem adicional para evitar handovers prematuros
DEFAULT_CIO_DB = 0.0  # Offset padrão da célula (dB)
DEFAULT_TTT_S = 0.064  # Tempo padrão para trigger: 64ms
DEFAULT_HYSTERESIS_DB = 0.0  # Hysteresis padrão: 0 dB

# ============================================================
# PARÂMETROS DOS EQUIPAMENTOS DE USUÁRIO (UE - User Equipment)
# ============================================================
# Define as características dos dispositivos móveis:
# - Ganho de antena do UE: 0 dB (antena isotrópica)
# - Altura do usuário: 1.6 metros (altura típica handheld)
# - Perda no cabo do UE: 0 dB (dispositivo pequeno)
# - Sensibilidade de recepção: -80 dBm (mínimo para detecção)

UE_ANTENNA_GAIN_DB = 0.0  # Ganho da antena do UE em dB
UE_HEIGHT_M = 1.6  # Altura típica do usuário em metros
UE_CABLE_LOSS_DB = 0.0  # Perda no cabo do UE (desprezível)
UE_RX_SENSITIVITY_DBM = -80.0  # Sensibilidade mínima de recepção em dBm
UE_RX_SENSITIVITY_MARGIN_DB = 0.0  # Tolerância adicional para handover/conexão por desvio de fading
UE_MIMO_LAYERS = 2  # Configuração MIMO 2x2

# Velocidades de movimento:
# - Pedestre: 5 m/s
# - Veículo: 25 m/s
# - Probabilidade de mudança de direção: 0.06% por passo
PEDESTRIAN_PROB = 0.80  # 80% dos usuários são pedestres
PEDESTRIAN_SPEED = 5.0  # Velocidade de pedestres em m/s
VEHICLE_SPEED = 25.0  # Velocidade de veículos em m/s
DIRECTION_CHANGE_PROB = 0.0006  # Probabilidade de mudar direção por step

# ============================================================
# PERFIS DE USUÁRIO (USER PROFILES)
# ============================================================
# Define três tipos de usuários com diferentes requisitos de taxa:
# - low: 96 kbps (voz, messaging) - 60% dos usuários
# - medium: 5 Mbps (video streaming básico) - 30% dos usuários
# - high: 24 Mbps (4K video, gaming) - 10% dos usuários
# Cada perfil tem cor associada para visualização no mapa

USER_PROFILES = {
    "low": {
        "bitrate_bps": 96e3,  # 96 kbps - voz/mensagens
        "prob": 0.60,  # 60% dos usuários são deste tipo
        "color": "green"  # Cor para visualização
    },
    "medium": {
        "bitrate_bps": 5e6,  # 5 Mbps - video streaming
        "prob": 0.30,  # 30% dos usuários
        "color": "yellow"  # Cor para visualização
    },
    "high": {
        "bitrate_bps": 24e6,  # 24 Mbps - 4K/gaming
        "prob": 0.10,  # 10% dos usuários
        "color": "red"  # Cor para visualização
    }
}

# ============================================================
# MODELO DE TRÁFEGO E CONEXÃO
# ============================================================
# Define parâmetros estocásticos para geração de tráfego:
# - Tempo entre tentativas de conexão: distribuição normal
# - Duração da conexão: distribuição normal
# Usamos distribuição normal truncada (valores mínimos)

CONNECTION_ATTEMPT_MEAN = 20.0  # Média de tempo entre tentativas (s)
CONNECTION_ATTEMPT_STD = 3.0  # Desvio padrão do tempo entre tentativas

CONNECTION_DURATION_MEAN = 60.0  # Média de duração da conexão (s)
CONNECTION_DURATION_STD = 15.0  # Desvio padrão da duração

# ============================================================
# MODELO DE PROPAGAÇÃO
# ============================================================
# Define perdas adicionais no modelo de propagação:
# - Body loss: perda por absorção do corpo do usuário (1 dB)
# - Slow fading margin: margem para desvanecimento lento (shadowing)
# - Foliage loss: perda por vegetação/obstáculos (4 dB)
# - Interference margin: margem para interferência de outras células
# - Rain margin: margem para atenuação por chuva (0 = não considerado)
# - Noise figure: figura de ruído do receptor (7 dB)
# - Thermal noise: ruído térmico base (-174 dBm/Hz)

BODY_LOSS_DB = 1.0  # Perda por absorção do corpo
SLOW_FADING_MARGIN_DB = 4.0  # Margem para shadowing
FOLIAGE_LOSS_DB = 4.0  # Perda por vegetação
INTERFERENCE_MARGIN_DB = 2.0  # Margem de interferência
RAIN_MARGIN_DB = 0.0  # Margem de chuva (não considerada)

NOISE_FIGURE_DB = 7.0  # Figura de ruído do receptor
THERMAL_NOISE_DBM_HZ = -174.0  # Densidade de potência de ruído térmico

# ============================================================
# RECURSOS DE RADIO (PRB - Physical Resource Blocks)
# ============================================================
# Define a estrutura de recursos de radio:
# - PRB: menor unidade de alocação de recursos (180 kHz)
# - Total de PRBs por BS = bandwidth / PRB_bandwidth
# Ex: 20 MHz / 180 kHz = 111 PRBs (arredondado)

PRB_BANDWIDTH_HZ = 180e3  # Largura de banda de um PRB: 180 kHz
TOTAL_PRBS_PER_BS = int(BANDWIDTH_HZ / PRB_BANDWIDTH_HZ)  # PRBs por BS

# ============================================================
# RIC (RAN Intelligent Controller) E xApps
# ============================================================
# O-RAN utiliza RIC (RAN Intelligent Controller) para controle:
# - Near-RT RIC: controle em tempo real (10-100ms)
# - Non-RT RIC: controle em segundos/minutos
# 
# xApps são aplicações que executam no RIC:
# - MRO (Mobility Robustness Optimization): otimiza parâmetros de handover
# - MLB (Load Balancing): distribui carga entre células
# - PINGPONG_PERIOD: tempo para detectar ping-pong (10s)
# - MRO_WINDOW: janela para cálculo de métricas MRO (240s)
# - RLF thresholds: limites para detecção de falha de enlace

RIC_CONTROL_PERIOD = 10.0  # Período de atualização do RIC (s)
MRO_WINDOW = 240.0  # Janela para cálculo de métricas MRO (s)
PINGPONG_PERIOD = 10.0  # Período para detectar ping-pong (s)
CMF_MODE = "no_CM"
CMF_MODES = ("no_CM", "prio_MRO", "prio_MLB")
STATISTICS_IGNORE_INITIAL_S = 150.0  # Ignora a instabilidade inicial nas estatisticas finais

# Thresholds para detecção de RLF (Radio Link Failure)
RLF_SINR_THRESHOLD_DB = -6.0  # SINR mínimo: -6 dB
RLF_RSRP_THRESHOLD_DBM = -110.0  # RSRP mínimo: -110 dBm

# ============================================================
# TABELAS DE DECISÃO DOS xApps
# ============================================================
# Funções de decisão (Policy Tables) para os xApps:
# 
# choose_ttt_from_pingpong_ratio:
# - Ajusta TTT baseado na razão de ping-pong
# - Ping-pong ratio = handovers ping-pong / total handovers
# - TTT maior reduz ping-pongs mas pode causar RLF
#
# choose_hysteresis_from_rlf_ratio:
# - Ajusta hysteresis baseado na razão de RLF
# - RLF ratio = RLFs / total handovers
# - Hysteresis maior reduz handovers desnecessários
#
# choose_cio_from_load:
# - Ajusta CIO (Cell Individual Offset) baseado na carga
# - CIO positivo: atrai mais usuários (célula mais "forte")
# - CIO negativo: repele usuários (célula mais "fraca")

def choose_ttt_from_pingpong_ratio(ratio):
    """Seleciona TTT (Time To Trigger) baseado na razão de ping-pong conforme o artigo."""
    if ratio <= 0.2667:
        return 0.08
    if ratio <= 0.3333:
        return 0.10
    if ratio <= 0.4000:
        return 0.128
    if ratio <= 0.4667:
        return 0.16
    if ratio <= 0.5333:
        return 0.256
    if ratio <= 0.6000:
        return 0.32
    if ratio <= 0.6667:
        return 0.48
    if ratio <= 0.7333:
        return 0.512
    if ratio <= 0.8000:
        return 0.64
    if ratio <= 0.8667:
        return 1.024
    if ratio <= 0.9333:
        return 1.28
    return 2.56


def choose_hysteresis_from_rlf_ratio(ratio):
    """Seleciona hysteresis baseado na razão de RLF conforme o artigo."""
    if ratio <= 0.15:
        return 1.0
    if ratio <= 0.20:
        return 1.5
    if ratio <= 0.25:
        return 2.0
    if ratio <= 0.30:
        return 2.5
    if ratio <= 0.35:
        return 3.0
    if ratio <= 0.40:
        return 3.5
    if ratio <= 0.45:
        return 4.0
    if ratio <= 0.50:
        return 4.5
    if ratio <= 0.55:
        return 5.0
    if ratio <= 0.60:
        return 5.5
    if ratio <= 0.65:
        return 6.0
    if ratio <= 0.70:
        return 6.5
    if ratio <= 0.75:
        return 7.0
    if ratio <= 0.80:
        return 7.5
    if ratio <= 0.85:
        return 8.0
    if ratio <= 0.90:
        return 8.5
    if ratio <= 0.95:
        return 9.0
    return 9.5


def choose_cio_from_load(load):
    """Seleciona CIO (Cell Individual Offset) baseado na carga da célula conforme o artigo."""
    if load <= 0.4545:
        return 0.0
    if load <= 0.5455:
        return 0.5
    if load <= 0.6364:
        return 1.0
    if load <= 0.7273:
        return 1.5
    if load <= 0.8182:
        return 2.0
    if load <= 0.9091:
        return 2.5
    return 3.0


def _mro_conflict_priority(bs):
    """Retorna True se a BS estiver em condição que prioriza MRO sobre MLB."""
    total_ho = len(bs.ho_events)
    if total_ho == 0:
        return False
    pp_ratio = len(bs.pingpong_events) / total_ho
    rlf_ratio = len(bs.rlf_events) / total_ho
    return pp_ratio > 0.2667 or rlf_ratio > 0.15


def _mlb_priority(bs):
    """Retorna True se a carga da BS indica que MLB deve ter prioridade."""
    return bs.load() > 0.8182


# ============================================================
# CLASSES DE DADOS
# ============================================================
# Define as estruturas de dados principais:
#
# BaseStation (Dataclass):
# - Representa uma estação base com posição, parâmetros de transmissão
# - Armazena contadores de eventos: handovers, ping-pongs, RLFs
# - Armazena parâmetros ajustáveis: CIO, TTT, hysteresis
# - Armazena PRBs utilizados (used_prbs)
#
# User (Dataclass):
# - Representa um equipamento de usuário (UE)
# - Armazena posição, velocidade, direção
# - Armazena estado de conexão: serving_bs, connected, allocated_prbs
# - Armazena contadores de mobilidade: handovers, ping-pongs, RLFs
# - Armazena temporizadores: TTT, candidate_bs

@dataclass
class BaseStation:
    """Classe que representa uma estação base (eNodeB/gNodeB)."""
    bs_id: int  # Identificador único da BS
    x: float  # Posição X em metros
    y: float  # Posição Y em metros

    # Parâmetros de transmissão
    tx_power_dbm: float = BS_TX_POWER_DBM
    antenna_gain_db: float = BS_ANTENNA_GAIN_DB
    height_m: float = BS_HEIGHT_M
    cable_loss_db: float = BS_CABLE_LOSS_DB

    # Parâmetros de handover ajustados pelo RIC
    cio_db: float = DEFAULT_CIO_DB  # Cell Individual Offset
    ttt_s: float = DEFAULT_TTT_S  # Time To Trigger
    hysteresis_db: float = DEFAULT_HYSTERESIS_DB  # Hysteresis

    # Recursos utilizados
    used_prbs: int = 0  # PRBs atualmente alocados

    # Filas de eventos (para métricas do RIC)
    ho_events: deque = field(default_factory=deque)  # Timestamps de handover
    pingpong_events: deque = field(default_factory=deque)  # Timestamps de ping-pong
    rlf_events: deque = field(default_factory=deque)  # Timestamps de RLF

    def load(self):
        """Calcula a carga da BS (PRBs utilizados / total de PRBs)."""
        return self.used_prbs / TOTAL_PRBS_PER_BS


@dataclass
class User:
    """Classe que representa um equipamento de usuário (UE)."""
    ue_id: int  # Identificador único do UE
    x: float  # Posição X em metros
    y: float  # Posição Y em metros
    speed: float  # Velocidade de movimento (m/s)
    direction: float  # Direção de movimento (radianos)
    profile_name: str  # Nome do perfil de tráfego
    bitrate_bps: float  # Taxa de bits requerida (bps)
    color: str  # Cor para visualização

    # Estado de conexão
    serving_bs: int = None  # Índice da BS que serve o UE
    connected: bool = False  # Flag de conexão
    allocated_prbs: int = 0  # PRBs alocados ao UE

    # Controle de conexão
    next_attempt_time: float = 0.0  # Próxima tentativa de conexão
    connection_end_time: float = 0.0  # Tempo de fim da conexão

    # Estado de handover
    candidate_bs: int = None  # BS candidata para handover
    ttt_timer: float = 0.0  # Temporizador TTT

    # Histórico de mobilidade
    last_handover_time: float = -9999.0  # Tempo do último handover
    last_bs_before_ho: int = None  # BS anterior ao último handover

    # Contadores globais
    total_handovers: int = 0  # Total de handovers realizados
    total_pingpongs: int = 0  # Total de ping-pongs
    total_rlfs: int = 0  # Total de RLFs
    total_connected_time: float = 0.0  # Tempo total conectado


# ============================================================
# GEOMETRIA DA REDE
# ============================================================
# Funções para geração da topologia da rede:
#
# generate_19_bs_hex_grid:
# - Gera 19 estações base em layout hexagonal
# - Utiliza sistema de coordenadas axiais (q, r, s) onde s = -q - r
# - Layout típico de redes celulares (classe de hexágonos)
# - Centro em (1000, 1000) metros
#
# simulation_polygon:
# - Define a área de simulação (polígono irregular)
# - Representa a área de cobertura válida
#
# point_inside_polygon:
# - Algoritmo ray-casting para verificar se ponto está dentro do polígono
# - Usado para garantir que usuários fiquem dentro da área de cobertura
#
# random_point_inside:
# - Gera ponto aleatório dentro do polígono
# - Utilizado para posicionar usuários iniciais

def generate_19_bs_hex_grid(isd=None, center_x=1000, center_y=1000, n_bs=None):
    """Gera estações base em layout hexagonal (grid de anéis).
    
    Args:
        isd: Inter-Site Distance (distância entre sites) em metros
        center_x: Coordenada X do centro do grid
        center_y: Coordenada Y do centro do grid
    
    Returns:
        Lista de objetos BaseStation em posições hexagonais
    """
    if isd is None:
        isd = INTER_SITE_DISTANCE
    if n_bs is None:
        n_bs = N_BS
    n_bs = max(1, int(n_bs))

    coords = []

    rings = 0
    while 1 + 3 * rings * (rings + 1) < n_bs:
        rings += 1
    for q in range(-rings, rings + 1):
        for r in range(-rings, rings + 1):
            s = -q - r  # Coordenada axial s
            if max(abs(q), abs(r), abs(s)) <= rings:
                # Conversão de coordenadas axiais para cartesianas
                x = center_x + isd * np.sqrt(3) * (q + r / 2)
                y = center_y + isd * 1.5 * r
                coords.append((x, y))

    if len(coords) > n_bs:
        coords = sorted(coords, key=lambda p: ((p[0] - center_x) ** 2 + (p[1] - center_y) ** 2, p[1], p[0]))[:n_bs]

    # Ordena por Y depois por X para visualização
    coords = sorted(coords, key=lambda p: (p[1], p[0]))
    return [BaseStation(i + 1, x, y) for i, (x, y) in enumerate(coords)]


def _convex_hull(points):
    """Calcula a envoltória convexa dos pontos usando monotonic chain."""
    pts = sorted({(float(x), float(y)) for x, y in points})
    if len(pts) <= 1:
        return np.array(pts)

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for point in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)

    upper = []
    for point in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)

    return np.array(lower[:-1] + upper[:-1])


def _expand_polygon_from_centroid(poly, margin_m):
    """Expande o polígono radialmente para aproximar a borda de cobertura."""
    if len(poly) == 0:
        return poly

    center = poly.mean(axis=0)
    expanded = []
    for point in poly:
        vector = point - center
        norm = np.linalg.norm(vector)
        if norm < 1e-9:
            expanded.append(point)
        else:
            expanded.append(center + vector / norm * (norm + margin_m))
    return np.array(expanded)


def simulation_polygon(bs_list=None, coverage_margin_m=None):
    """Define dinamicamente o polígono que representa a área de simulação.

    O polígono é calculado a partir da envoltória das estações base e expandido
    por uma margem de cobertura. Assim, mudanças em N_BS ou INTER_SITE_DISTANCE
    ajustam automaticamente a área onde os usuários são criados e se movem.

    Args:
        bs_list: Lista de estações base usadas na simulação.
        coverage_margin_m: Margem extra em metros ao redor das BSs externas.

    Returns:
        Array numpy com coordenadas dos vértices do polígono
    """
    if bs_list is None:
        bs_list = generate_19_bs_hex_grid(n_bs=N_BS)

    margin_m = (
        float(coverage_margin_m)
        if coverage_margin_m is not None
        else float(INTER_SITE_DISTANCE) * float(SIMULATION_AREA_MARGIN_FACTOR)
    )
    margin_m = max(margin_m, 1.0)
    points = np.array([[bs.x, bs.y] for bs in bs_list], dtype=float)

    if len(points) == 0:
        return np.array([])

    if len(points) < 3:
        min_x, min_y = points.min(axis=0) - margin_m
        max_x, max_y = points.max(axis=0) + margin_m
        return np.array([
            [min_x, min_y],
            [max_x, min_y],
            [max_x, max_y],
            [min_x, max_y],
        ])

    hull = _convex_hull(points)
    return _expand_polygon_from_centroid(hull, margin_m)


def point_inside_polygon(x, y, poly):
    """Verifica se um ponto (x, y) está dentro de um polígono.
    
    Usa o algoritmo ray-casting (método do raio):
    - Traça um raio horizontal a partir do ponto
    - Conta quantas arestas o raio atravessa
    - Se o número for ímpar, o ponto está dentro
    
    Args:
        x: Coordenada X do ponto
        y: Coordenada Y do ponto
        poly: Array numpy com vértices do polígono
    
    Returns:
        True se o ponto está dentro, False caso contrário
    """
    inside = False
    j = len(poly) - 1  # Começa pelo último vértice

    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]

        # Verifica se o raio cruza a aresta
        intersect = ((yi > y) != (yj > y)) and \
            (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi)

        if intersect:
            inside = not inside  # Alterna o estado

        j = i

    return inside


def random_point_inside(poly):
    """Gera um ponto aleatório dentro do polígono.
    
    Método:
    - Gera ponto aleatório na bounding box
    - Verifica se está dentro do polígono
    - Repete até encontrar ponto válido
    
    Args:
        poly: Array numpy com vértices do polígono
    
    Returns:
        Tupla (x, y) com coordenadas do ponto
    """
    min_x, min_y = poly.min(axis=0)
    max_x, max_y = poly.max(axis=0)

    while True:
        x = np.random.uniform(min_x, max_x)
        y = np.random.uniform(min_y, max_y)

        if point_inside_polygon(x, y, poly):
            return x, y


# ============================================================
# MODELO DE PROPAGAÇÃO 3GPP-STYLE UMa (Urban Macro)
# ============================================================
# Implementa o modelo de propagação 3GPP 38.901 para cenário UMa:
#
# Funções de conversão de unidades:
# - dbm_to_mw: converte dBm para miliwatts
# - mw_to_dbm: converte miliwatts para dBm
#
# Funções de distância:
# - distance_2d: distância euclidiana 2D (projeção horizontal)
# - distance_3d: distância 3D (considera diferença de altura)
#
# Funções de perda de caminho:
# - pathloss_uma_nlos_38901: perda de caminho NLOS (Non-Line-of-Sight)
# - total_extra_losses_db: soma de perdas adicionais
# - rx_power_dbm: potência recebida (com shadowing)
# - rx_power_dbm_no_fast_random: potência sem fast fading (para decisão)

def dbm_to_mw(dbm):
    """Converte potência em dBm para miliwatts.
    
    Args:
        dbm: Potência em dBm
    
    Returns:
        Potência em miliwatts
    """
    return 10 ** (dbm / 10)


def mw_to_dbm(mw):
    """Converte potência em miliwatts para dBm.
    
    Args:
        mw: Potência em miliwatts
    
    Returns:
        Potência em dBm
    """
    return 10 * np.log10(mw + 1e-30)


def distance_2d(bs, ue):
    """Calcula distância 2D entre BS e UE (projeção no plano horizontal).
    
    Args:
        bs: Objeto BaseStation
        ue: Objeto User
    
    Returns:
        Distância em metros
    """
    return np.sqrt((bs.x - ue.x) ** 2 + (bs.y - ue.y) ** 2)


def distance_3d(bs, ue):
    """Calcula distância 3D entre BS e UE (considera diferença de altura).
    
    Args:
        bs: Objeto BaseStation
        ue: Objeto User
    
    Returns:
        Distância em metros
    """
    d2d = distance_2d(bs, ue)
    return np.sqrt(d2d ** 2 + (bs.height_m - UE_HEIGHT_M) ** 2)


def pathloss_uma_nlos_38901(d3d_m, fc_ghz=CENTER_FREQ_GHZ):
    """Calcula perda de caminho segundo 3GPP 38.901 para UMa NLOS.
    
    Fórmula: PL = 13.54 + 39.08*log10(d3d) + 20*log10(fc) - 0.6*(h_ue - 1.5)
    
    Args:
        d3d_m: Distância 3D em metros (mínimo 10m)
        fc_ghz: Frequência central em GHz
    
    Returns:
        Perda de caminho em dB
    """
    d3d_m = max(d3d_m, 10.0)  # Distância mínima de 10m

    pl = (
        13.54
        + 39.08 * np.log10(d3d_m)
        + 20.0 * np.log10(fc_ghz)
        - 0.6 * (UE_HEIGHT_M - 1.5)
    )

    return pl


def total_extra_losses_db():
    """Calcula a soma de todas as perdas adicionais do modelo.
    
    Inclui: body loss, slow fading, foliage, interference, rain
    
    Returns:
        Total de perdas adicionais em dB
    """
    return (
        BODY_LOSS_DB
        + SLOW_FADING_MARGIN_DB
        + FOLIAGE_LOSS_DB
        + INTERFERENCE_MARGIN_DB
        + RAIN_MARGIN_DB
    )


def rx_power_dbm(bs, ue):
    """Calcula potência de recepção em dBm.
    
    Modelo: P_rx = P_tx + G_antena_bs + G_antena_ue - P_cabos - PL - perdas
    
    Args:
        bs: Objeto BaseStation
        ue: Objeto User
    
    Returns:
        Potência recebida em dBm
    """
    d3d = distance_3d(bs, ue)
    pl = pathloss_uma_nlos_38901(d3d)

    # Shadowing: desvanecimento lento (log-normal, σ = 4 dB)
    shadowing = np.random.normal(0, 4.0)

    rx = (
        bs.tx_power_dbm
        + bs.antenna_gain_db
        + UE_ANTENNA_GAIN_DB
        - bs.cable_loss_db
        - UE_CABLE_LOSS_DB
        - pl
        - total_extra_losses_db()
        - shadowing
    )

    return rx


def rx_power_dbm_no_fast_random(bs, ue):
    """Calcula potência de recepção sem componente aleatório (shadowing).
    
    Usado para decisões de handover (média estatística).
    
    Args:
        bs: Objeto BaseStation
        ue: Objeto User
    
    Returns:
        Potência média recebida em dBm
    """
    d3d = distance_3d(bs, ue)
    pl = pathloss_uma_nlos_38901(d3d)

    rx = (
        bs.tx_power_dbm
        + bs.antenna_gain_db
        + UE_ANTENNA_GAIN_DB
        - bs.cable_loss_db
        - UE_CABLE_LOSS_DB
        - pl
        - total_extra_losses_db()
    )

    return rx


def noise_power_dbm():
    """Calcula potência de ruído térmico em dBm.
    
    Fórmula: P_noise = -174 + 10*log10(BW) + NF
    
    Returns:
        Potência de ruído em dBm
    """
    return THERMAL_NOISE_DBM_HZ + 10 * np.log10(BANDWIDTH_HZ) + NOISE_FIGURE_DB


def calculate_sinr_db(ue, bs_list, serving_bs_index):
    """Calcula o SINR (Signal to Interference plus Noise Ratio).
    
    SINR = P_sinal / (P_interferência + P_ruído)
    
    Args:
        ue: Objeto User
        bs_list: Lista de todas as BSs
        serving_bs_index: Índice da BS que serve o UE
    
    Returns:
        Tupla (SINR em dB, array de potências recebidas)
    """
    # Calcula potência recebida de todas as BSs
    rx_powers_dbm = np.array([rx_power_dbm(bs, ue) for bs in bs_list])

    # Potência do sinal desejado
    signal_mw = dbm_to_mw(rx_powers_dbm[serving_bs_index])
    
    # Potência de interferência (todas as outras BSs)
    interference_mw = np.sum(dbm_to_mw(rx_powers_dbm)) - signal_mw
    
    # Potência de ruído
    noise_mw = dbm_to_mw(noise_power_dbm())

    # SINR linear
    sinr = signal_mw / (interference_mw + noise_mw)

    # Converte para dB
    return 10 * np.log10(sinr + 1e-30), rx_powers_dbm


def spectral_efficiency_from_sinr(sinr_db):
    """Calcula eficiência espectral a partir do SINR.
    
    Usa a fórmula de Shannon: C = log2(1 + SINR)
    Limitada a 6 bps/Hz (limite teórico de 64-QAM)
    
    Args:
        sinr_db: SINR em dB
    
    Returns:
        Eficiência espectral em bps/Hz
    """
    sinr_linear = 10 ** (sinr_db / 10)

    se = np.log2(1 + sinr_linear)

    return min(se, 6.0)  # Limita a 6 bps/Hz (64-QAM)


def required_prbs_for_user(ue, sinr_db):
    """Calcula o número de PRBs necessários para um usuário.
    
    Args:
        ue: Objeto User
        sinr_db: SINR em dB
    
    Returns:
        Número de PRBs necessários
    """
    se = spectral_efficiency_from_sinr(sinr_db)
    capacity_per_prb = PRB_BANDWIDTH_HZ * se

    if capacity_per_prb <= 1:
        return TOTAL_PRBS_PER_BS + 1  # Não cabe em uma célula

    return int(np.ceil(ue.bitrate_bps / capacity_per_prb))


def user_throughput_satisfaction(ue, bs_list):
    """Calcula a satisfacao do UE conectado pelo throughput entregue/demandado.

    Retorna um valor entre 0 e 1. Usuarios desconectados ou sem demanda ativa
    nao entram na media de satisfacao da rede.
    """
    if not ue.connected or ue.serving_bs is None or ue.allocated_prbs <= 0 or ue.bitrate_bps <= 0:
        return float("nan")

    sinr_db, _ = calculate_sinr_db(ue, bs_list, ue.serving_bs)
    se = spectral_efficiency_from_sinr(sinr_db)
    delivered_bps = ue.allocated_prbs * PRB_BANDWIDTH_HZ * se
    return float(np.clip(delivered_bps / ue.bitrate_bps, 0.0, 1.0))


def mean_user_satisfaction(users, bs_list):
    """Calcula a satisfacao media dos usuarios conectados."""
    values = [
        user_throughput_satisfaction(ue, bs_list)
        for ue in users
        if ue.connected
    ]
    values = [value for value in values if np.isfinite(value)]
    return float(np.mean(values)) if values else float("nan")


# ============================================================
# CRIAÇÃO E GERENCIAMENTO DE USUÁRIOS
# ============================================================
# Funções para geração e controle de usuários:
#
# sample_profile:
# - Seleciona um perfil de usuário baseado em probabilidades
# - Retorna nome do perfil, taxa de bits e cor
#
# normal_positive:
# - Gera valor de distribuição normal truncado (mínimo 0.1)
# - Usado para tempos de conexão e tentativas
#
# generate_next_attempt_time:
# - Gera tempo para próxima tentativa de conexão
#
# generate_connection_duration:
# - Gera duração da conexão
#
# create_users:
# - Cria todos os usuários iniciais com posições aleatórias

def sample_profile():
    """Seleciona um perfil de usuário aleatoriamente.
    
    Baseado nas probabilidades definidas em USER_PROFILES:
    - 60% low (96 kbps)
    - 30% medium (5 Mbps)
    - 10% high (24 Mbps)
    
    Returns:
        Tupla (nome do perfil, bitrate, cor)
    """
    names = list(USER_PROFILES.keys())
    probs = [USER_PROFILES[n]["prob"] for n in names]
    selected = np.random.choice(names, p=probs)

    profile = USER_PROFILES[selected]

    return selected, profile["bitrate_bps"], profile["color"]


def normal_positive(mean, std, min_value=0.1):
    """Gera valor de distribuição normal truncado (mínimo positivo).
    
    Args:
        mean: Média da distribuição
        std: Desvio padrão
        min_value: Valor mínimo permitido
    
    Returns:
        Valor gerado
    """
    value = np.random.normal(mean, std)
    return max(value, min_value)


def generate_next_attempt_time(current_time):
    """Gera tempo para próxima tentativa de conexão.
    
    Args:
        current_time: Tempo atual da simulação
    
    Returns:
        Tempo da próxima tentativa
    """
    return current_time + normal_positive(
        CONNECTION_ATTEMPT_MEAN,
        CONNECTION_ATTEMPT_STD,
        min_value=1.0
    )


def generate_connection_duration():
    """Gera duração aleatória da conexão.
    
    Returns:
        Duração em segundos
    """
    return normal_positive(
        CONNECTION_DURATION_MEAN,
        CONNECTION_DURATION_STD,
        min_value=1.0
    )


def create_users(poly):
    """Cria todos os usuários iniciais com posições aleatórias.
    
    Args:
        poly: Polígono da área de simulação
    
    Returns:
        Lista de objetos User
    """
    users = []

    for i in range(N_USERS):
        # Gera posição aleatória dentro do polígono
        x, y = random_point_inside(poly)

        # Divide usuários entre pedestres e veículos conforme a configuração.
        is_pedestrian = np.random.rand() < PEDESTRIAN_PROB
        speed = PEDESTRIAN_SPEED if is_pedestrian else VEHICLE_SPEED
        direction = np.random.uniform(0, 2 * np.pi)

        # Seleciona perfil de tráfego
        profile_name, bitrate, color = sample_profile()

        # Cria objeto User
        ue = User(
            ue_id=i,
            x=x,
            y=y,
            speed=speed,
            direction=direction,
            profile_name=profile_name,
            bitrate_bps=bitrate,
            color=color
        )

        # Inicializa temporizador de conexão
        ue.next_attempt_time = generate_next_attempt_time(0.0)

        users.append(ue)

    return users


# ============================================================
# ASSOCIAÇÃO E HANDOVER
# ============================================================
# Implementa o gerenciamento de conexão e handover:
#
# best_bs_by_rsrp:
# - Encontra a melhor BS por RSRP (Reference Signal Received Power)
# - Considera CIO (Cell Individual Offset) no cálculo
#
# nearest_or_best_bs_initial:
# - Versão simplificada para associação inicial
#
# release_connection:
# - Libera a conexão do UE, retornando PRBs à BS
#
# try_establish_connection:
# - Tenta estabelecer conexão com uma BS
# - Verifica sensibilidade e disponibilidade de PRBs
#
# perform_handover:
# - Executa handover entre BSs
# - Atualiza contadores e registra eventos
#
# a3_handover_logic:
# - Implementa Event A3 do 3GPP (melhor célula por offset)
# - Usa TTT (Time To Trigger) e hysteresis

def best_bs_by_rsrp(ue, bs_list):
    """Encontra a melhor BS por RSRP (Reference Signal Received Power).
    
    RSRP = potência de referência recebida + CIO
    O CIO permite balanceamento de carga entre células
    
    Args:
        ue: Objeto User
        bs_list: Lista de BSs
    
    Returns:
        Tupla (índice da melhor BS, array de RSRPs)
    """
    rsrp = np.array([
        rx_power_dbm_no_fast_random(bs, ue) + bs.cio_db
        for bs in bs_list
    ])

    best_index = int(np.argmax(rsrp))

    return best_index, rsrp


def nearest_or_best_bs_initial(ue, bs_list):
    """Associação inicial simplificada (melhor RSRP).
    
    Args:
        ue: Objeto User
        bs_list: Lista de BSs
    
    Returns:
        Índice da BS selecionada
    """
    best_index, _ = best_bs_by_rsrp(ue, bs_list)
    return best_index


def release_connection(ue, bs_list):
    """Libera a conexão do UE, retornando PRBs à BS.
    
    Args:
        ue: Objeto User
        bs_list: Lista de BSs
    """
    if ue.connected and ue.serving_bs is not None:
        bs_list[ue.serving_bs].used_prbs -= ue.allocated_prbs
        bs_list[ue.serving_bs].used_prbs = max(0, bs_list[ue.serving_bs].used_prbs)

    ue.connected = False
    ue.allocated_prbs = 0
    ue.serving_bs = None
    ue.candidate_bs = None
    ue.ttt_timer = 0.0


def try_establish_connection(ue, bs_list, current_time):
    """Tenta estabelecer conexão com uma BS.
    
    Processo:
    1. Ordena BSs por RSRP (melhor para pior)
    2. Para cada BS, verifica:
       - Sensibilidade do UE (RSRP > -80 dBm)
       - PRBs disponíveis
    3. Primeira BS que satisfaz condições ganha a conexão
    
    Args:
        ue: Objeto User
        bs_list: Lista de BSs
        current_time: Tempo atual
    
    Returns:
        True se conexão estabelecida, False caso contrário
    """
    candidate_order = []

    # Calcula RSRP de todas as BSs
    rsrp = np.array([
        rx_power_dbm_no_fast_random(bs, ue) + bs.cio_db
        for bs in bs_list
    ])

    # Ordena por RSRP (decrescente)
    candidate_order = list(np.argsort(rsrp)[::-1])

    # Tenta conectar à melhor BS disponível
    for bs_idx in candidate_order:
        bs = bs_list[bs_idx]

        # Calcula SINR e potências
        sinr_db, rx_powers = calculate_sinr_db(ue, bs_list, bs_idx)

        # Verifica sensibilidade do UE com margem de tolerância para handover/conexão
        sensitivity_threshold = UE_RX_SENSITIVITY_DBM - UE_RX_SENSITIVITY_MARGIN_DB
        if rx_powers[bs_idx] < sensitivity_threshold:
            continue

        # Calcula PRBs necessários
        prbs = required_prbs_for_user(ue, sinr_db)

        # Verifica disponibilidade de PRBs
        if bs.used_prbs + prbs <= TOTAL_PRBS_PER_BS:
            bs.used_prbs += prbs

            ue.connected = True
            ue.serving_bs = bs_idx
            ue.allocated_prbs = prbs
            ue.connection_end_time = current_time + generate_connection_duration()

            return True

    return False


def perform_handover(ue, bs_list, target_bs_idx, current_time):
    """Executa handover do UE para nova BS.
    
    Processo:
    1. Libera PRBs da BS origem
    2. Aloca PRBs na BS destino
    3. Atualiza contadores de eventos
    4. Detecta ping-pong (retorno em < 10s)
    
    Args:
        ue: Objeto User
        bs_list: Lista de BSs
        target_bs_idx: Índice da BS destino
        current_time: Tempo atual
    
    Returns:
        Dicionário com dados do handover se bem-sucedido, None caso contrário
    """
    source_bs_idx = ue.serving_bs

    source_bs = bs_list[source_bs_idx]
    target_bs = bs_list[target_bs_idx]

    # Calcula SINR na nova célula
    sinr_db, rx_powers = calculate_sinr_db(ue, bs_list, target_bs_idx)

    # Verifica sensibilidade usando margem de tolerância para evitar falhas por desvio de fading
    sensitivity_threshold = UE_RX_SENSITIVITY_DBM - UE_RX_SENSITIVITY_MARGIN_DB
    if rx_powers[target_bs_idx] < sensitivity_threshold:
        return False

    # Calcula PRBs necessários na nova célula
    required_prbs = required_prbs_for_user(ue, sinr_db)

    # Verifica disponibilidade de PRBs
    if target_bs.used_prbs + required_prbs > TOTAL_PRBS_PER_BS:
        return False

    # Libera PRBs da célula origem
    source_bs.used_prbs -= ue.allocated_prbs
    source_bs.used_prbs = max(0, source_bs.used_prbs)

    # Aloca PRBs na célula destino
    target_bs.used_prbs += required_prbs

    # Mantém histórico do último handover antes de atualizar a conexão
    previous_bs_before_ho = ue.last_bs_before_ho
    old_last_ho_time = ue.last_handover_time
    ue.last_bs_before_ho = source_bs_idx

    # Atualiza estado do UE
    ue.serving_bs = target_bs_idx
    ue.allocated_prbs = required_prbs
    ue.total_handovers += 1
    ue.last_handover_time = current_time

    # Registra evento de handover
    source_bs.ho_events.append(current_time)

    handover_event = {
        "time": float(current_time),
        "previous bs": int(source_bs.bs_id),
        "current bs": int(target_bs.bs_id),
        "user": int(ue.ue_id),
        "conn_sinr": float(sinr_db),
        "x pos": float(ue.x),
        "y pos": float(ue.y),
        "pingpong": None,
    }

    # Detecta ping-pong: retorno à BS anterior em < 10s
    if (
        old_last_ho_time > 0
        and current_time - old_last_ho_time <= PINGPONG_PERIOD
        and target_bs_idx == previous_bs_before_ho
    ):
        ue.total_pingpongs += 1
        source_bs.pingpong_events.append(current_time)
        handover_event["pingpong"] = {
            "time": float(current_time),
            "current bs": int(target_bs.bs_id),
            "user": int(ue.ue_id),
            "conn_sinr": float(sinr_db),
            "x pos": float(ue.x),
            "y pos": float(ue.y),
            "ho pp time": float(current_time - old_last_ho_time),
        }

    return handover_event


def a3_handover_logic(ue, bs_list, current_time, dt):
    """Implementa lógica de handover Event A3 (3GPP).
    
    Condição de trigger:
    - Melhor célula > (célula atual + hysteresis) por TTT
    
    Parâmetros:
    - TTT: Time To Trigger (tempo mínimo para confirmar)
    - Hysteresis: margem de decisão
    
    Args:
        ue: Objeto User
        bs_list: Lista de BSs
        current_time: Tempo atual
        dt: Passo de tempo

    Returns:
        Dicionário com dados do handover se ocorrer, None caso contrário
    """
    if not ue.connected:
        return None

    current_idx = ue.serving_bs
    current_bs = bs_list[current_idx]

    # Encontra melhor BS
    best_idx, rsrp = best_bs_by_rsrp(ue, bs_list)

    # Se já está na melhor célula, reseta temporizadores
    if best_idx == current_idx:
        ue.candidate_bs = None
        ue.ttt_timer = 0.0
        return None

    current_rsrp = rsrp[current_idx]
    target_rsrp = rsrp[best_idx]

    # Condição A3: target > current + hysteresis
    a3_condition = target_rsrp > current_rsrp + current_bs.hysteresis_db

    if a3_condition:
        # Se mesma候选, incrementa temporizador
        if ue.candidate_bs == best_idx:
            ue.ttt_timer += dt
        else:
            # Nova候选, reseta temporizador
            ue.candidate_bs = best_idx
            ue.ttt_timer = dt

        # Verifica se TTT foi atingido
        if ue.ttt_timer >= current_bs.ttt_s:
            handover_event = perform_handover(ue, bs_list, best_idx, current_time)
            ue.candidate_bs = None
            ue.ttt_timer = 0.0
            return handover_event
    else:
        # Condição não satisfeita, reseta
        ue.candidate_bs = None
        ue.ttt_timer = 0.0

    return None


# ============================================================
# MOBILIDADE DOS USUÁRIOS
# ============================================================
# Implementa o modelo de mobilidade dos usuários:
#
# - Movimentação retilínea com direção constante
# - Probabilidade de mudança de direção a cada passo
# - Reflexão nas bordas da área de simulação
#
# O modelo considera:
# - Usuários pedestres: 5 m/s
# - Usuários veículos: 25 m/s
# - Mudança de direção: 0.06% de probabilidade por passo

def update_user_position(ue, poly):
    """Atualiza a posição do usuário considerando mobilidade.
    
    Processo:
    1. Possível mudança de direção (probabilidade baixa)
    2. Movimentação baseada em velocidade e direção
    3. Verificação de permanência dentro do polígono
    4. Reflexão se atingir bordas
    
    Args:
        ue: Objeto User
        poly: Polígono da área de simulação
    """
    # Probabilidade de mudança de direção
    if np.random.rand() < DIRECTION_CHANGE_PROB:
        ue.direction = np.random.uniform(0, 2 * np.pi)

    # Salva posição anterior para reflexão
    old_x, old_y = ue.x, ue.y

    # Atualiza posição: x += v * cos(θ) * dt
    ue.x += ue.speed * np.cos(ue.direction) * DT
    ue.y += ue.speed * np.sin(ue.direction) * DT

    # Verifica se está dentro do polígono
    if not point_inside_polygon(ue.x, ue.y, poly):
        # Reflexão: mantém posição anterior e muda direção
        ue.x, ue.y = old_x, old_y
        ue.direction = np.random.uniform(0, 2 * np.pi)


# ============================================================
# RLF (RADIO LINK FAILURE)
# ============================================================
# Implementa a detecção de falha de enlace rádio:
#
# RLF ocorre quando:
# - SINR cai abaixo do limiar (-6 dB) OU
# - RSRP cai abaixo do limiar (-110 dBm)
#
# Quando RLF é detectado:
# 1. Conexão é liberada
# 2. Evento de RLF é registrado
# 3. Contador do UE é incrementado
# 4. Nova tentativa de conexão é agendada

def check_rlf(ue, bs_list, current_time):
    """Verifica se ocorreu Radio Link Failure.
    
    RLF é detectado quando:
    - SINR < RLF_SINR_THRESHOLD_DB (-6 dB) OU
    - RSRP < RLF_RSRP_THRESHOLD_DBM (-110 dBm)
    
    Args:
        ue: Objeto User
        bs_list: Lista de BSs
        current_time: Tempo atual
    
    Returns:
        Dicionário com dados do RLF se detectado, None caso contrário
    """
    if not ue.connected:
        return None

    # Calcula SINR e potências
    sinr_db, rx_powers = calculate_sinr_db(ue, bs_list, ue.serving_bs)
    rsrp = rx_powers[ue.serving_bs]

    # Verifica thresholds de RLF
    if sinr_db < RLF_SINR_THRESHOLD_DB or rsrp < RLF_RSRP_THRESHOLD_DBM:
        serving_bs = bs_list[ue.serving_bs]
        rlf_event = {
            "time": float(current_time),
            "current bs": int(serving_bs.bs_id),
            "user": int(ue.ue_id),
            "conn_sinr": float(sinr_db),
            "x pos": float(ue.x),
            "y pos": float(ue.y),
        }

        # Registra evento de RLF na BS
        serving_bs.rlf_events.append(current_time)
        
        # Incrementa contador do UE
        ue.total_rlfs += 1

        # Libera conexão
        release_connection(ue, bs_list)
        
        # Agenda nova tentativa
        ue.next_attempt_time = generate_next_attempt_time(current_time)

        return rlf_event

    return None


# ============================================================
# nRT-RIC / xApps (Near-Real Time RAN Intelligent Controller)
# ============================================================
# Implementa as funções do RIC (RAN Intelligent Controller):
#
# O-RAN utiliza uma arquitetura de duas camadas:
# - Non-RT RIC: controle em escala de segundos/minutos
# - Near-RT RIC: controle em tempo real (10-100ms)
#
# xApps são aplicações que executam no Near-RT RIC:
#
# 1. MRO (Mobility Robustness Optimization):
#    - Otimiza parâmetros de handover (TTT, hysteresis)
#    - Reduz ping-pongs e RLFs
#    - Janela de análise: 240 segundos
#
# 2. MLB (Load Balancing):
#    - Ajusta CIO para balancear carga entre células
#    - Move usuários de células sobrecarregadas
#
# Funções:
# - cleanup_old_events: remove eventos antigos da janela
# - ric_mro_update: atualiza parâmetros MRO
# - ric_mlb_update: atualiza parâmetros MLB
# - ric_update: coordena ambas as funções

def cleanup_old_events(bs_list, current_time):
    """Remove eventos antigos fora da janela MRO.
    
    Mantém apenas eventos dos últimos MRO_WINDOW segundos
    para cálculo de métricas atualizadas.
    
    Args:
        bs_list: Lista de BSs
        current_time: Tempo atual
    """
    min_time = current_time - MRO_WINDOW

    for bs in bs_list:
        # Remove handovers antigos
        while bs.ho_events and bs.ho_events[0] < min_time:
            bs.ho_events.popleft()

        # Remove ping-pongs antigos
        while bs.pingpong_events and bs.pingpong_events[0] < min_time:
            bs.pingpong_events.popleft()

        # Remove RLFs antigos
        while bs.rlf_events and bs.rlf_events[0] < min_time:
            bs.rlf_events.popleft()


def ric_mro_update(bs_list, current_time):
    """Atualiza parâmetros de Mobility Robustness Optimization.
    
    Calcula métricas:
    - Ping-pong ratio = ping-pongs / handovers
    - RLF ratio = RLFs / handovers
    
    Ajusta:
    - TTT: tempo para trigger de handover
    - Hysteresis: margem de decisão
    
    Args:
        bs_list: Lista de BSs
        current_time: Tempo atual
    """
    # Limpa eventos antigos
    cleanup_old_events(bs_list, current_time)

    for bs in bs_list:
        # Conta eventos na janela
        total_ho = len(bs.ho_events)
        total_pp = len(bs.pingpong_events)
        total_rlf = len(bs.rlf_events)

        # Calcula razões
        pp_ratio = total_pp / total_ho if total_ho > 0 else 0.0
        rlf_ratio = total_rlf / total_ho if total_ho > 0 else 0.0

        # Ajusta parâmetros usando tabelas de decisão
        bs.ttt_s = choose_ttt_from_pingpong_ratio(pp_ratio)
        bs.hysteresis_db = choose_hysteresis_from_rlf_ratio(rlf_ratio)


def ric_mlb_update(bs_list):
    """Atualiza parâmetros de Load Balancing (CIO).
    
    Ajusta Cell Individual Offset baseado na carga em faixas definidas pelo artigo.
    
    Args:
        bs_list: Lista de BSs
    """
    for bs in bs_list:
        bs.cio_db = choose_cio_from_load(bs.load())


def ric_update(bs_list, current_time, mode=CMF_MODE):
    """Coordena atualização de todos os xApps do RIC.
    
    Executa em período definido (RIC_CONTROL_PERIOD = 10s).
    Suporta três modos do Conflict Mitigation Framework:
    - no_CM: aplica MRO e MLB sem resolução de prioridade
    - prio_MRO: prioriza ajustes de MRO quando há instabilidade
    - prio_MLB: prioriza ajustes de MLB quando há carga alta

    Args:
        bs_list: Lista de BSs
        current_time: Tempo atual
        mode: Modo de conflito do RIC
    """
    if mode not in CMF_MODES:
        raise ValueError(f"Modo CMF desconhecido: {mode}")

    if mode == "no_CM":
        ric_mro_update(bs_list, current_time)
        ric_mlb_update(bs_list)
        return

    if mode == "prio_MRO":
        ric_mro_update(bs_list, current_time)
        for bs in bs_list:
            if not _mro_conflict_priority(bs):
                bs.cio_db = choose_cio_from_load(bs.load())
        return

    if mode == "prio_MLB":
        ric_mlb_update(bs_list)
        for bs in bs_list:
            if not _mlb_priority(bs):
                total_ho = len(bs.ho_events)
                total_pp = len(bs.pingpong_events)
                total_rlf = len(bs.rlf_events)
                pp_ratio = total_pp / total_ho if total_ho > 0 else 0.0
                rlf_ratio = total_rlf / total_ho if total_ho > 0 else 0.0
                bs.ttt_s = choose_ttt_from_pingpong_ratio(pp_ratio)
                bs.hysteresis_db = choose_hysteresis_from_rlf_ratio(rlf_ratio)
        return


def _format_csv_float(value, decimals=4):
    """Formata floats para CSV mantendo pelo menos uma casa decimal."""
    if not np.isfinite(value):
        return "nan"
    rounded = round(float(value), decimals)
    text = f"{rounded:.{decimals}f}".rstrip("0").rstrip(".")
    if "." not in text:
        text += ".0"
    return text


def _record_bs_state(bs_history, bs_list, current_time):
    """Registra estado por estação base no formato dos CSVs de resultados."""
    for bs in bs_list:
        availability = max(0.0, min(1.0, 1.0 - bs.load()))
        bs_history[bs.bs_id].append({
            "time": float(current_time),
            "current bs": int(bs.bs_id),
            "availability": availability,
            "cio": float(bs.cio_db),
            "hyst": float(bs.hysteresis_db),
            "ttt": float(bs.ttt_s),
        })


def _load_balance_ratio(loads):
    """Calcula o índice de Jain para balanceamento de carga."""
    loads = np.array(loads, dtype=float)
    squared_sum = np.sum(loads ** 2)
    if squared_sum <= 0:
        return float("nan")
    return float((np.sum(loads) ** 2) / (len(loads) * squared_sum))


def _statistics_mask(time_values):
    """Retorna a mascara da janela usada nos indicadores do artigo."""
    return np.asarray(time_values, dtype=float) >= STATISTICS_IGNORE_INITIAL_S


def summarize_performance(results):
    """Calcula as metricas finais ignorando os primeiros 150 segundos."""
    mask = _statistics_mask(results["time"])
    if not np.any(mask):
        mask = np.ones_like(results["time"], dtype=bool)

    satisfaction = results["satisfaction"][mask]
    finite_satisfaction = satisfaction[np.isfinite(satisfaction)]

    return {
        "mean_bs_load": float(np.mean(results["avg_load"][mask])),
        "mean_user_satisfaction": float(np.mean(finite_satisfaction)) if len(finite_satisfaction) else 0.0,
        "total_blocked_attempts": int(np.sum(results["blocked_attempts"][mask])),
        "total_rlfs": int(np.sum(results["rlfs"][mask])),
        "total_handovers": int(np.sum(results["handovers"][mask])),
        "total_pingpongs": int(np.sum(results["pingpongs"][mask])),
    }


def _csv_timestamp():
    now = datetime.now()
    weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return f"{weekdays[now.weekday()]}_{months[now.month - 1]}_{now.day}_{now.hour:02d}-{now.minute:02d}-{now.second:02d}_{now.year}"


def _csv_suffix(cmf_mode):
    suffix_by_mode = {
        "no_CM": "MROMLB",
        "prio_MRO": "prioMRO",
        "prio_MLB": "prioMLB",
    }
    bandwidth_mhz = int(BANDWIDTH_HZ / 1e6)
    return f"{_csv_timestamp()}_{bandwidth_mhz}_{suffix_by_mode.get(cmf_mode, cmf_mode)}"


def _write_bs_result_csvs(bs_history, cmf_mode):
    """Escreve um CSV por BS em simulation_results/<modo>."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "simulation_results"))
    mode_dir = os.path.join(base_dir, cmf_mode)
    os.makedirs(mode_dir, exist_ok=True)

    timestamp = _csv_suffix(cmf_mode)
    written_files = []

    for bs_id in sorted(bs_history):
        path = os.path.join(mode_dir, f"bs-{bs_id}_{timestamp}.csv")
        with open(path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["time", "current bs", "availability", "cio", "hyst", "ttt"])
            for row in bs_history[bs_id]:
                writer.writerow([
                    _format_csv_float(row["time"], 1),
                    row["current bs"],
                    _format_csv_float(row["availability"], 4),
                    _format_csv_float(row["cio"], 4),
                    _format_csv_float(row["hyst"], 4),
                    _format_csv_float(row["ttt"], 4),
                ])
        written_files.append(path)

    return written_files


def _write_load_balance_csv(load_balance_history, cmf_mode):
    """Escreve a série temporal do índice de balanceamento no formato lb_*.csv."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "simulation_results"))
    mode_dir = os.path.join(base_dir, cmf_mode)
    os.makedirs(mode_dir, exist_ok=True)

    timestamp = _csv_suffix(cmf_mode)
    path = os.path.join(mode_dir, f"lb_{timestamp}.csv")

    with open(path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["time", "lb ratio"])
        for row in load_balance_history:
            writer.writerow([
                _format_csv_float(row["time"], 1),
                _format_csv_float(row["lb ratio"], 16),
            ])

    return path


def _write_availability_csv(availability_history, cmf_mode):
    """Escreve a série temporal da disponibilidade média em simulation_results/<modo>."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "simulation_results"))
    mode_dir = os.path.join(base_dir, cmf_mode)
    os.makedirs(mode_dir, exist_ok=True)

    timestamp = _csv_suffix(cmf_mode)
    path = os.path.join(mode_dir, f"avail_{timestamp}.csv")

    with open(path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["time", "availability"])
        for row in availability_history:
            writer.writerow([
                _format_csv_float(row["time"], 1),
                _format_csv_float(row["availability"], 16),
            ])

    return path


def _write_satisfaction_csv(satisfaction_history, cmf_mode):
    """Escreve a série temporal de satisfação média de usuários em simulation_results/<modo>."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "simulation_results"))
    mode_dir = os.path.join(base_dir, cmf_mode)
    os.makedirs(mode_dir, exist_ok=True)

    timestamp = _csv_suffix(cmf_mode)
    path = os.path.join(mode_dir, f"satis_{timestamp}.csv")

    with open(path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["time", "satisfaction"])
        for row in satisfaction_history:
            writer.writerow([
                _format_csv_float(row["time"], 1),
                _format_csv_float(row["satisfaction"], 16),
            ])

    return path


def _write_connection_block_csv(blocked_connection_events, cmf_mode):
    """Escreve eventos de conexões bloqueadas no formato cb_*.csv."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "simulation_results"))
    mode_dir = os.path.join(base_dir, cmf_mode)
    os.makedirs(mode_dir, exist_ok=True)

    timestamp = _csv_suffix(cmf_mode)
    path = os.path.join(mode_dir, f"cb_{timestamp}.csv")

    with open(path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["time", "user", "x pos", "y pos"])
        for event in blocked_connection_events:
            writer.writerow([
                _format_csv_float(event["time"], 12),
                event["user"],
                _format_csv_float(event["x pos"], 12),
                _format_csv_float(event["y pos"], 12),
            ])

    return path


def _write_handover_csv(handover_events, cmf_mode):
    """Escreve eventos de handover no formato ho_*.csv."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "simulation_results"))
    mode_dir = os.path.join(base_dir, cmf_mode)
    os.makedirs(mode_dir, exist_ok=True)

    timestamp = _csv_suffix(cmf_mode)
    path = os.path.join(mode_dir, f"ho_{timestamp}.csv")

    with open(path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["time", "previous bs", "current bs", "user", "conn_sinr", "x pos", "y pos"])
        for event in handover_events:
            writer.writerow([
                _format_csv_float(event["time"], 12),
                event["previous bs"],
                event["current bs"],
                event["user"],
                _format_csv_float(event["conn_sinr"], 12),
                _format_csv_float(event["x pos"], 12),
                _format_csv_float(event["y pos"], 12),
            ])

    return path


def _write_pingpong_csv(pingpong_events, cmf_mode):
    """Escreve eventos de ping-pong no formato pp_*.csv."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "simulation_results"))
    mode_dir = os.path.join(base_dir, cmf_mode)
    os.makedirs(mode_dir, exist_ok=True)

    timestamp = _csv_suffix(cmf_mode)
    path = os.path.join(mode_dir, f"pp_{timestamp}.csv")

    with open(path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["time", "current bs", "user", "conn_sinr", "x pos", "y pos", "ho pp time"])
        for event in pingpong_events:
            writer.writerow([
                _format_csv_float(event["time"], 12),
                event["current bs"],
                event["user"],
                _format_csv_float(event["conn_sinr"], 12),
                _format_csv_float(event["x pos"], 12),
                _format_csv_float(event["y pos"], 12),
                _format_csv_float(event["ho pp time"], 12),
            ])

    return path


def _write_rlf_csv(rlf_events, cmf_mode):
    """Escreve eventos de Radio Link Failure no formato rlf_*.csv."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "simulation_results"))
    mode_dir = os.path.join(base_dir, cmf_mode)
    os.makedirs(mode_dir, exist_ok=True)

    timestamp = _csv_suffix(cmf_mode)
    path = os.path.join(mode_dir, f"rlf_{timestamp}.csv")

    with open(path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["time", "current bs", "user", "conn_sinr", "x pos", "y pos"])
        for event in rlf_events:
            writer.writerow([
                _format_csv_float(event["time"], 12),
                event["current bs"],
                event["user"],
                _format_csv_float(event["conn_sinr"], 12),
                _format_csv_float(event["x pos"], 12),
                _format_csv_float(event["y pos"], 12),
            ])

    return path


def run_simulation(show_progress=False, step_callback=None, stop_event=None, cmf_mode=CMF_MODE, export_bs_results=True):
    """Executa a simulação completa da rede celular.
    
    Args:
        show_progress: Se True, imprime o progresso da simulação.
        step_callback: Função chamada a cada passo com o snapshot atual.
        stop_event: threading.Event para interromper a simulação.
        export_bs_results: Se True, gera CSV por BS em simulation_results/<modo>.

    Returns:
        Tupla (bs_list, users, poly, results)
    """
    # Inicializa rede
    bs_list = generate_19_bs_hex_grid(n_bs=N_BS)
    poly = simulation_polygon(bs_list)
    users = create_users(poly)

    # Listas para histórico de métricas
    time_history = []
    avg_load_history = []
    max_load_history = []
    connected_users_history = []
    satisfaction_history_steps = []
    handover_history = []
    pingpong_history = []
    rlf_history = []
    blocked_attempts_history = []
    bs_history = {bs.bs_id: [] for bs in bs_list}
    load_balance_history = []
    availability_history = []
    satisfaction_history = []
    blocked_connection_events = []
    handover_events = []
    pingpong_events = []
    rlf_events = []

    # Contadores acumulados
    total_blocked_attempts = 0
    last_total_ho = 0
    last_total_pp = 0
    last_total_rlf = 0
    stats_total_ho = 0
    stats_total_pp = 0
    stats_total_rlf = 0
    stats_total_blocked = 0
    stats_load_sum = 0.0
    stats_satisfaction_sum = 0.0
    stats_satisfaction_samples = 0
    stats_samples = 0

    # Próxima atualização do RIC
    next_ric_time = 0.0
    next_bs_log_time = 0.0

    # Loop principal de simulação
    for step in range(STEPS):
        current_time = step * DT

        # Atualiza parâmetros do RIC a cada 10 segundos
        if current_time >= next_ric_time:
            ric_update(bs_list, current_time, cmf_mode)
            next_ric_time += RIC_CONTROL_PERIOD

        blocked_this_step = 0

        # Processa cada usuário
        for ue in users:
            # Atualiza posição
            update_user_position(ue, poly)

            if ue.connected:
                # Usuário conectado: atualiza tempo
                ue.total_connected_time += DT

                # Verifica fim de conexão
                if current_time >= ue.connection_end_time:
                    release_connection(ue, bs_list)
                    ue.next_attempt_time = generate_next_attempt_time(current_time)
                    continue

                # Verifica RLF
                rlf_event = check_rlf(ue, bs_list, current_time)
                if rlf_event is not None:
                    rlf_events.append(rlf_event)
                    continue

                # Executa lógica de handover
                handover_event = a3_handover_logic(ue, bs_list, current_time, DT)
                if handover_event is not None:
                    handover_events.append(handover_event)
                    if handover_event["pingpong"] is not None:
                        pingpong_events.append(handover_event["pingpong"])

            else:
                # Usuário desconectado: tenta conectar
                if current_time >= ue.next_attempt_time:
                    established = try_establish_connection(ue, bs_list, current_time)

                    if not established:
                        blocked_connection_events.append({
                            "time": float(current_time),
                            "user": int(ue.ue_id),
                            "x pos": float(ue.x),
                            "y pos": float(ue.y),
                        })
                        total_blocked_attempts += 1
                        blocked_this_step += 1
                        ue.next_attempt_time = generate_next_attempt_time(current_time)

        # Coleta métricas globais
        total_ho = sum(ue.total_handovers for ue in users)
        total_pp = sum(ue.total_pingpongs for ue in users)
        total_rlf = sum(ue.total_rlfs for ue in users)
        ho_this_step = total_ho - last_total_ho
        pp_this_step = total_pp - last_total_pp
        rlf_this_step = total_rlf - last_total_rlf

        loads = [bs.load() for bs in bs_list]
        connected_users = sum(1 for ue in users if ue.connected)
        satisfaction = mean_user_satisfaction(users, bs_list)

        # Registra no histórico
        time_history.append(current_time)
        avg_load_history.append(np.mean(loads))
        max_load_history.append(np.max(loads))
        connected_users_history.append(connected_users)
        satisfaction_history_steps.append(satisfaction)

        handover_history.append(ho_this_step)
        pingpong_history.append(pp_this_step)
        rlf_history.append(rlf_this_step)
        blocked_attempts_history.append(blocked_this_step)

        if current_time >= STATISTICS_IGNORE_INITIAL_S:
            stats_total_ho += ho_this_step
            stats_total_pp += pp_this_step
            stats_total_rlf += rlf_this_step
            stats_total_blocked += blocked_this_step
            stats_load_sum += float(np.mean(loads))
            if np.isfinite(satisfaction):
                stats_satisfaction_sum += satisfaction
                stats_satisfaction_samples += 1
            stats_samples += 1

        # Atualiza contadores
        last_total_ho = total_ho
        last_total_pp = total_pp
        last_total_rlf = total_rlf

        if current_time + 1e-12 >= next_bs_log_time:
            _record_bs_state(bs_history, bs_list, next_bs_log_time)
            load_balance_history.append({
                "time": float(next_bs_log_time),
                "lb ratio": _load_balance_ratio(loads),
            })
            availability_history.append({
                "time": float(next_bs_log_time),
                "availability": float(np.mean([1.0 - load for load in loads])),
            })
            satisfaction_history.append({
                "time": float(next_bs_log_time),
                "satisfaction": satisfaction,
            })
            next_bs_log_time += 1.0

        if step_callback is not None:
            stats_satisfaction = (
                stats_satisfaction_sum / stats_satisfaction_samples
                if stats_satisfaction_samples > 0
                else (satisfaction if np.isfinite(satisfaction) else 0.0)
            )
            snapshot = {
                "step": step + 1,
                "steps": STEPS,
                "time": current_time,
                "progress": round((step + 1) * 100.0 / max(STEPS, 1), 1),
                "connected_users": connected_users,
                "satisfaction": stats_satisfaction,
                "avg_load": stats_load_sum / stats_samples if stats_samples > 0 else float(np.mean(loads)),
                "max_load": float(np.max(loads)),
                "handovers": stats_total_ho,
                "pingpongs": stats_total_pp,
                "rlfs": stats_total_rlf,
                "blocked_attempts": blocked_this_step,
                "total_blocked_attempts": stats_total_blocked,
                "raw_handovers": total_ho,
                "raw_pingpongs": total_pp,
                "raw_rlfs": total_rlf,
                "raw_total_blocked_attempts": total_blocked_attempts,
                "statistics_start_time": STATISTICS_IGNORE_INITIAL_S,
                "area_polygon": [
                    {"x": float(point[0]), "y": float(point[1])}
                    for point in poly
                ],
                "bs": [
                    {
                        "id": bs.bs_id,
                        "x": float(bs.x),
                        "y": float(bs.y),
                        "load": float(bs.load()),
                        "used_prbs": int(bs.used_prbs),
                    }
                    for bs in bs_list
                ],
                "ues": [
                    {
                        "id": ue.ue_id,
                        "x": float(ue.x),
                        "y": float(ue.y),
                        "color": ue.color,
                        "connected": bool(ue.connected),
                        "serving_bs": ue.serving_bs,
                        "speed": float(ue.speed),
                    }
                    for ue in users
                ],
            }
            step_callback(snapshot)

        if stop_event is not None and stop_event.is_set():
            break

        if show_progress and (step % max(1, STEPS // 40) == 0 or step == STEPS - 1):
            percent = (step + 1) * 100.0 / STEPS
            print(f"\rSimulação: passo {step + 1}/{STEPS} ({percent:.1f}%)", end="", flush=True)

    if show_progress:
        print()

    # Compila resultados
    results = {
        "time": np.array(time_history),
        "avg_load": np.array(avg_load_history),
        "max_load": np.array(max_load_history),
        "connected_users": np.array(connected_users_history),
        "satisfaction": np.array(satisfaction_history_steps),
        "handovers": np.array(handover_history),
        "pingpongs": np.array(pingpong_history),
        "rlfs": np.array(rlf_history),
        "blocked_attempts": np.array(blocked_attempts_history),
        "total_blocked_attempts": total_blocked_attempts,
        "statistics_start_time": STATISTICS_IGNORE_INITIAL_S,
    }
    results["performance_summary"] = summarize_performance(results)

    if export_bs_results:
        results["bs_result_files"] = _write_bs_result_csvs(bs_history, cmf_mode)
        results["load_balance_file"] = _write_load_balance_csv(load_balance_history, cmf_mode)
        results["availability_file"] = _write_availability_csv(availability_history, cmf_mode)
        results["satisfaction_file"] = _write_satisfaction_csv(satisfaction_history, cmf_mode)
        results["connection_block_file"] = _write_connection_block_csv(blocked_connection_events, cmf_mode)
        results["handover_file"] = _write_handover_csv(handover_events, cmf_mode)
        results["pingpong_file"] = _write_pingpong_csv(pingpong_events, cmf_mode)
        results["rlf_file"] = _write_rlf_csv(rlf_events, cmf_mode)

    return bs_list, users, poly, results


def run_simulation_worker(seed, cmf_mode=CMF_MODE):
    """Executa uma simulação independente em processo separado."""
    np.random.seed(seed)
    bs_list, users, poly, results = run_simulation(show_progress=False, cmf_mode=cmf_mode, export_bs_results=False)
    summary = results["performance_summary"]
    return {
        "seed": seed,
        "mean_bs_load": summary["mean_bs_load"],
        "mean_user_satisfaction": summary["mean_user_satisfaction"],
        "total_handovers": summary["total_handovers"],
        "total_pingpongs": summary["total_pingpongs"],
        "total_rlfs": summary["total_rlfs"],
        "total_blocked_attempts": summary["total_blocked_attempts"],
        "connected_final": int(results["connected_users"][-1]),
    }


def run_simulation_parallel(repetitions=2, workers=None, cmf_mode=CMF_MODE):
    workers = workers or os.cpu_count() or 1
    print(f"Executando {repetitions} simulações em paralelo usando {workers} workers...")
    seeds = [42 + i for i in range(repetitions)]
    metrics = []

    def format_progress(completed, total, width=30):
        pct = completed / total
        filled = int(pct * width)
        bar = "#" * filled + "-" * (width - filled)
        return f"[{bar}] {completed}/{total} ({pct * 100:.1f}%)"

    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(run_simulation_worker, seed, cmf_mode) for seed in seeds]

        for completed, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            metrics.append(future.result())
            print(f"\r{format_progress(completed, repetitions)}", end="", flush=True)

    print()
    return metrics


# ============================================================
# VISUALIZAÇÃO E PLOTS
# ============================================================
# Funções para visualização dos resultados da simulação:
#
# plot_topology:
# - Plota a topologia da rede (BSs e usuários)
# - Mostra a área de simulação (polígono)
# - Marca posições das BSs e usuários
#
# plot_results:
# - Plota métricas ao longo do tempo:
#   a) Usuários conectados
#   b) Carga média e máxima das BSs
#   c) Eventos acumulados (handovers, ping-pongs, RLFs)
#   d) Tentativas bloqueadas acumuladas

def plot_topology(bs_list, users, poly):
    """Plota a topologia da rede celular simulada.
    
    Mostra:
    - Polígono da área de simulação
    - Posições das 19 estações base (marcadores azuis)
    - Posições dos 380 usuários (pontos coloridos por perfil)
    
    Args:
        bs_list: Lista de estações base
        users: Lista de usuários
        poly: Polígono da área
    """
    plt.figure(figsize=(8, 8))

    # Desenha polígono da área
    closed_poly = np.vstack([poly, poly[0]])
    plt.plot(closed_poly[:, 0], closed_poly[:, 1], color="black", linewidth=2)

    # Plota estações base
    for bs in bs_list:
        plt.scatter(bs.x, bs.y, marker="1", s=120, color="blue")
        plt.text(bs.x + 40, bs.y + 40, str(bs.bs_id), color="blue", fontsize=10)

    # Plota usuários
    for ue in users:
        plt.scatter(ue.x, ue.y, s=14, color=ue.color)

    plt.xlabel("x")
    plt.ylabel("y")
    plt.title("Simulation area, 19 base stations and 380 users")
    plt.grid(True)
    plt.axis("equal")
    plt.show()


def plot_results(results):
    """Plota gráficos com as métricas da simulação.
    
    Gera 4 gráficos:
    1. Usuários conectados ao longo do tempo
    2. Carga média e máxima das BSs
    3. Eventos de mobilidade acumulados
    4. Tentativas bloqueadas acumuladas
    
    Args:
        results: Dicionário com resultados da simulação
    """
    t = results["time"]

    # Gráfico 1: Usuários conectados
    plt.figure(figsize=(9, 4))
    plt.plot(t, results["connected_users"])
    plt.xlabel("Tempo [s]")
    plt.ylabel("Usuários conectados")
    plt.title("Usuários conectados ao longo do tempo")
    plt.grid(True)
    plt.show()

    # Gráfico 2: Carga das BSs
    plt.figure(figsize=(9, 4))
    plt.plot(t, results["avg_load"], label="Carga média")
    plt.plot(t, results["max_load"], label="Carga máxima")
    plt.xlabel("Tempo [s]")
    plt.ylabel("Carga PRB")
    plt.title("Carga das base stations")
    plt.legend()
    plt.grid(True)
    plt.show()

    # Gráfico 3: Eventos de mobilidade
    plt.figure(figsize=(9, 4))
    plt.plot(t, np.cumsum(results["handovers"]), label="Handovers")
    plt.plot(t, np.cumsum(results["pingpongs"]), label="Ping-pongs")
    plt.plot(t, np.cumsum(results["rlfs"]), label="RLFs")
    plt.xlabel("Tempo [s]")
    plt.ylabel("Eventos acumulados")
    plt.title("Eventos de mobilidade")
    plt.legend()
    plt.grid(True)
    plt.show()

    # Gráfico 4: Tentativas bloqueadas
    plt.figure(figsize=(9, 4))
    plt.plot(t, np.cumsum(results["blocked_attempts"]))
    plt.xlabel("Tempo [s]")
    plt.ylabel("Tentativas bloqueadas acumuladas")
    plt.title("Bloqueios por falta de PRB")
    plt.grid(True)
    plt.show()


def print_summary(bs_list, users, results):
    """Imprime resumo dos resultados da simulação.
    
    Args:
        bs_list: Lista de estações base
        users: Lista de usuários
        results: Dicionário com resultados
    """
    # Calcula totais na janela estatistica do artigo.
    summary = results["performance_summary"]
    total_ho = summary["total_handovers"]
    total_pp = summary["total_pingpongs"]
    total_rlf = summary["total_rlfs"]

    connected_final = sum(1 for ue in users if ue.connected)

    # Imprime resultados gerais
    print("\n================ RESULTADOS GERAIS ================")
    print(f"Tempo simulado: {SIM_TIME:.1f} s")
    print(f"Base stations: {len(bs_list)}")
    print(f"Usuários: {len(users)}")
    print(f"PRBs por BS: {TOTAL_PRBS_PER_BS}")
    print(f"Janela estatistica: {STATISTICS_IGNORE_INITIAL_S:.0f}s a {SIM_TIME:.0f}s")
    print(f"Load medio das BSs: {summary['mean_bs_load'] * 100:.1f}%")
    print(f"Satisfacao media dos usuarios: {summary['mean_user_satisfaction'] * 100:.1f}%")
    print(f"Usuários conectados no fim: {connected_final}")
    print(f"Total de handovers: {total_ho}")
    print(f"Total de ping-pongs: {total_pp}")
    print(f"Total de RLFs: {total_rlf}")
    print(f"Tentativas bloqueadas: {summary['total_blocked_attempts']}")

    # Imprime razões
    if total_ho > 0:
        print(f"Razão ping-pong / handover: {total_pp / total_ho:.3f}")
        print(f"Razão RLF / handover: {total_rlf / total_ho:.3f}")

    # Imprime estado final das BSs
    print("\n================ ESTADO FINAL DAS BS ================")
    print("BS | Load | CIO | TTT | Hyst | Used PRB")
    print("----------------------------------------")

    for bs in bs_list:
        print(
            f"{bs.bs_id:2d} | "
            f"{bs.load():.2f} | "
            f"{bs.cio_db:5.1f} | "
            f"{bs.ttt_s:5.3f} | "
            f"{bs.hysteresis_db:4.1f} | "
            f"{bs.used_prbs:3d}"
        )


# ============================================================
# PROGRAMA PRINCIPAL (MAIN)
# ============================================================
# Ponto de entrada da simulação:
#
# 1. Executa run_simulation() que:
#    - Cria 19 BSs em grid hexagonal
#    - Cria 380 usuários com posições aleatórias
#    - Simula 1000 segundos de operação
#    - Coleta métricas de desempenho
#
# 2. Imprime resumo dos resultados (print_summary)
#
# 3. Gera visualizações (plot_topology, plot_results)
#
# O código pode ser executado diretamente com:
# python simulation.py

def parse_args():
    parser = argparse.ArgumentParser(description="Simulação O-RAN com progresso e execução paralela.")
    parser.add_argument("--runs", "-r", type=int, default=1, help="Número de simulações independentes a executar em paralelo")
    parser.add_argument("--workers", "-w", type=int, default=os.cpu_count() or 1, help="Número de workers a usar em ProcessPoolExecutor")
    parser.add_argument("--cmf-mode", type=str, default=CMF_MODE, choices=CMF_MODES, help="Modo do Conflict Mitigation Framework")
    parser.add_argument("--no-plots", action="store_true", help="Não exibir os gráficos ao final")
    return parser.parse_args()


def main():
    args = parse_args()

    cmf_mode = args.cmf_mode

    if args.runs <= 1:
        # Executa a simulação única com progresso
        bs_list, users, poly, results = run_simulation(show_progress=True, cmf_mode=cmf_mode)
        print(f"Modo CMF: {cmf_mode}")
        print_summary(bs_list, users, results)

        if not args.no_plots:
            plot_topology(bs_list, users, poly)
            plot_results(results)
        return

    # Executa simulações paralelas usando todos os núcleos disponíveis
    metrics = run_simulation_parallel(repetitions=args.runs, workers=args.workers, cmf_mode=cmf_mode)

    total_handovers = np.array([m["total_handovers"] for m in metrics])
    total_pingpongs = np.array([m["total_pingpongs"] for m in metrics])
    total_rlfs = np.array([m["total_rlfs"] for m in metrics])
    total_blocked = np.array([m["total_blocked_attempts"] for m in metrics])
    mean_load = np.array([m["mean_bs_load"] for m in metrics])
    mean_satisfaction = np.array([m["mean_user_satisfaction"] for m in metrics])
    connected_final = np.array([m["connected_final"] for m in metrics])

    print("\nResumo agregado das simulações paralelas:")
    print(f"Handovers médios: {total_handovers.mean():.1f} ± {total_handovers.std():.1f}")
    print(f"Ping-pongs médios: {total_pingpongs.mean():.1f} ± {total_pingpongs.std():.1f}")
    print(f"RLFs médios: {total_rlfs.mean():.1f} ± {total_rlfs.std():.1f}")
    print(f"Tentativas bloqueadas médias: {total_blocked.mean():.1f} ± {total_blocked.std():.1f}")
    print(f"Usuários conectados finais médios: {connected_final.mean():.1f} ± {connected_final.std():.1f}")


if __name__ == "__main__":
    main()
