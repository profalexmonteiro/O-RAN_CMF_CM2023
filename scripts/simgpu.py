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

import argparse
import sys

import numpy as np
import matplotlib.pyplot as plt
from dataclasses import dataclass, field
from collections import deque, defaultdict

try:
    import cupy as cp
    CUPY_AVAILABLE = True
except ImportError:
    cp = None
    CUPY_AVAILABLE = False

# Default backend is NumPy. Set to CuPy when --gpu is requested.
xp = np
random = np.random
USE_GPU = False
RNG_SEED = 42


def set_backend(use_gpu=False):
    """Configura o backend numérico para CPU (NumPy) ou GPU (CuPy)."""
    global xp, random, USE_GPU

    if use_gpu:
        if not CUPY_AVAILABLE:
            raise ImportError("CuPy não está instalado. Instale cupy ou execute sem --gpu.")

        xp = cp
        random = cp.random
        USE_GPU = True
    else:
        xp = np
        random = np.random
        USE_GPU = False

    initialize_random_seed(RNG_SEED)


def is_gpu_enabled():
    return USE_GPU and CUPY_AVAILABLE


def ensure_cpu(x):
    """Converte array CuPy para NumPy quando necessário."""
    if USE_GPU and cp is not None and isinstance(x, cp.ndarray):
        return cp.asnumpy(x)
    return x


def initialize_random_seed(seed):
    """Inicializa a semente de RNG para NumPy e CuPy."""
    np.random.seed(seed)
    if CUPY_AVAILABLE:
        try:
            cp.random.seed(seed)
        except Exception:
            pass

# ============================================================
# CONFIGURAÇÃO GERAL DA SIMULAÇÃO
# ============================================================
# Parâmetros globais que definem a estrutura da simulação:
# - N_BS: Número de estações base (19 em grid hexagonal)
# - USERS_PER_BS: Usuários por estação base
# - INTER_SITE_DISTANCE: Distância entre estações base (ISD)
# - SIM_TIME: Tempo total de simulação em segundos
# - DT: Passo de tempo (time step) da simulação

# Semente para reprodutibilidade dos resultados
initialize_random_seed(RNG_SEED)

N_BS = 19  # 19 estações base em layout hexagonal
USERS_PER_BS = 20  # 20 usuários por BS = 380 usuários total
N_USERS = N_BS * USERS_PER_BS  # Total de usuários na simulação

INTER_SITE_DISTANCE = 600.0  # Distância entre sites (metros)

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

# Velocidades de movimento:
# - Pedestre: 5 km/h (1.4 m/s)
# - Veículo: 25 km/h (6.9 m/s)
# - Probabilidade de mudança de direção: 0.06% por passo
PEDESTRIAN_SPEED = 5.0  # Velocidade de pedestres em km/h
VEHICLE_SPEED = 25.0  # Velocidade de veículos em km/h
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
        "color": "olive"  # Cor para visualização
    },
    "high": {
        "bitrate_bps": 24e6,  # 24 Mbps - 4K/gaming
        "prob": 0.10,  # 10% dos usuários
        "color": "darkred"  # Cor para visualização
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
    """Seleciona TTT (Time To Trigger) baseado na razão de ping-pong."""
    if ratio < 0.05:
        return 0.064  # TTT muito curto para ping-pong muito baixo
    elif ratio < 0.15:
        return 0.128  # TTT curto
    elif ratio < 0.30:
        return 0.256  # TTT médio
    else:
        return 0.512  # TTT longo para reduzir ping-pongs


def choose_hysteresis_from_rlf_ratio(ratio):
    """Seleciona hysteresis baseado na razão de RLF."""
    if ratio < 0.03:
        return 0.0  # Sem hysteresis
    elif ratio < 0.08:
        return 1.0  # 1 dB de hysteresis
    elif ratio < 0.15:
        return 2.0  # 2 dB de hysteresis
    else:
        return 3.0  # 3 dB de hysteresis (mais conservador)


def choose_cio_from_load(load):
    """Seleciona CIO (Cell Individual Offset) baseado na carga da célula."""
    if load < 0.35:
        return 3.0  # Baixa carga: attracts users
    elif load < 0.60:
        return 1.0  # Carga média-baixa
    elif load < 0.80:
        return 0.0  # Carga média
    elif load < 0.95:
        return -2.0  # Carga alta: repels users
    else:
        return -4.0  # Carga muito alta: repels strongly


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

def generate_19_bs_hex_grid(isd=600, center_x=1000, center_y=1000):
    """Gera 19 estações base em layout hexagonal (grid de anéis).
    
    Args:
        isd: Inter-Site Distance (distância entre sites) em metros
        center_x: Coordenada X do centro do grid
        center_y: Coordenada Y do centro do grid
    
    Returns:
        Lista de objetos BaseStation em posições hexagonais
    """
    coords = []

    rings = 2  # 2 anéis ao redor do centro = 19 células
    for q in range(-rings, rings + 1):
        for r in range(-rings, rings + 1):
            s = -q - r  # Coordenada axial s
            if max(abs(q), abs(r), abs(s)) <= rings:
                # Conversão de coordenadas axiais para cartesianas
                x = center_x + isd * np.sqrt(3) * (q + r / 2)
                y = center_y + isd * 1.5 * r
                coords.append((x, y))

    # Ordena por Y depois por X para visualização
    coords = sorted(coords, key=lambda p: (p[1], p[0]))
    return [BaseStation(i + 1, x, y) for i, (x, y) in enumerate(coords)]


def simulation_polygon():
    """Define o polígono que representa a área de simulação.
    
    Returns:
        Array numpy com coordenadas dos vértices do polígono
    """
    return np.array([
        [-2000, 1000],
        [-800, 3400],
        [-200, 4000],
        [2200, 4000],
        [2800, 3400],
        [3800, 1000],
        [2800, -1400],
        [2200, -2000],
        [-200, -2000],
        [-800, -1400],
    ])


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
        x = float(random.uniform(min_x, max_x))
        y = float(random.uniform(min_y, max_y))
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
    return 10 * xp.log10(mw + 1e-30)


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
        + 39.08 * xp.log10(d3d_m)
        + 20.0 * xp.log10(fc_ghz)
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
    shadowing = float(random.normal(0, 4.0))

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
    return THERMAL_NOISE_DBM_HZ + 10 * xp.log10(BANDWIDTH_HZ) + NOISE_FIGURE_DB


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
    rx_powers_dbm = xp.array([rx_power_dbm(bs, ue) for bs in bs_list])

    # Potência do sinal desejado
    signal_mw = dbm_to_mw(rx_powers_dbm[serving_bs_index])
    
    # Potência de interferência (todas as outras BSs)
    interference_mw = xp.sum(dbm_to_mw(rx_powers_dbm)) - signal_mw
    
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

    se = xp.log2(1 + sinr_linear)

    return min(float(se), 6.0)  # Limita a 6 bps/Hz (64-QAM)

    if capacity_per_prb <= 1:
        return TOTAL_PRBS_PER_BS + 1  # Não cabe em uma célula

    return int(np.ceil(ue.bitrate_bps / capacity_per_prb))


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
    value = float(random.normal(mean, std))
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

        # 80% pedestres, 20% veículos
        is_pedestrian = float(random.rand()) < 0.80
        speed = PEDESTRIAN_SPEED if is_pedestrian else VEHICLE_SPEED
        direction = float(random.uniform(0, 2 * np.pi))

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
    rsrp = xp.array([
        rx_power_dbm_no_fast_random(bs, ue) + bs.cio_db
        for bs in bs_list
    ])

    best_index = int(xp.argmax(rsrp))

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
    rsrp = xp.array([
        rx_power_dbm_no_fast_random(bs, ue) + bs.cio_db
        for bs in bs_list
    ])

    # Ordena por RSRP (decrescente)
    candidate_order = list(ensure_cpu(xp.argsort(rsrp))[::-1])

    # Tenta conectar à melhor BS disponível
    for bs_idx in candidate_order:
        bs = bs_list[bs_idx]

        # Calcula SINR e potências
        sinr_db, rx_powers = calculate_sinr_db(ue, bs_list, bs_idx)

        # Verifica sensibilidade do UE
        if rx_powers[bs_idx] < UE_RX_SENSITIVITY_DBM:
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
        True se handover bem-sucedido, False caso contrário
    """
    source_bs_idx = ue.serving_bs

    source_bs = bs_list[source_bs_idx]
    target_bs = bs_list[target_bs_idx]

    # Calcula SINR na nova célula
    sinr_db, rx_powers = calculate_sinr_db(ue, bs_list, target_bs_idx)

    # Verifica sensibilidade
    if rx_powers[target_bs_idx] < UE_RX_SENSITIVITY_DBM:
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

    # Atualiza histórico
    ue.last_bs_before_ho = source_bs_idx
    old_last_ho_time = ue.last_handover_time

    # Atualiza estado do UE
    ue.serving_bs = target_bs_idx
    ue.allocated_prbs = required_prbs
    ue.total_handovers += 1
    ue.last_handover_time = current_time

    # Registra evento de handover
    source_bs.ho_events.append(current_time)

    # Detecta ping-pong: retorno à BS anterior em < 10s
    if (
        old_last_ho_time > 0
        and current_time - old_last_ho_time <= PINGPONG_PERIOD
        and target_bs_idx == ue.last_bs_before_ho
    ):
        ue.total_pingpongs += 1
        source_bs.pingpong_events.append(current_time)

    return True


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
    """
    if not ue.connected:
        return

    current_idx = ue.serving_bs
    current_bs = bs_list[current_idx]

    # Encontra melhor BS
    best_idx, rsrp = best_bs_by_rsrp(ue, bs_list)

    # Se já está na melhor célula, reseta temporizadores
    if best_idx == current_idx:
        ue.candidate_bs = None
        ue.ttt_timer = 0.0
        return

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
            perform_handover(ue, bs_list, best_idx, current_time)
            ue.candidate_bs = None
            ue.ttt_timer = 0.0
    else:
        # Condição não satisfeita, reseta
        ue.candidate_bs = None
        ue.ttt_timer = 0.0


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
# - Usuários pedestres: 5 km/h
# - Usuários veículos: 25 km/h
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
    if float(random.rand()) < DIRECTION_CHANGE_PROB:
        ue.direction = float(random.uniform(0, 2 * np.pi))

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
        True se RLF detectado, False caso contrário
    """
    if not ue.connected:
        return False

    # Calcula SINR e potências
    sinr_db, rx_powers = calculate_sinr_db(ue, bs_list, ue.serving_bs)
    rsrp = rx_powers[ue.serving_bs]

    # Verifica thresholds de RLF
    if sinr_db < RLF_SINR_THRESHOLD_DB or rsrp < RLF_RSRP_THRESHOLD_DBM:
        # Registra evento de RLF na BS
        bs_list[ue.serving_bs].rlf_events.append(current_time)
        
        # Incrementa contador do UE
        ue.total_rlfs += 1

        # Libera conexão
        release_connection(ue, bs_list)
        
        # Agenda nova tentativa
        ue.next_attempt_time = generate_next_attempt_time(current_time)

        return True

    return False


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
    
    Ajusta Cell Individual Offset baseado na carga:
    - Carga baixa (< 35%): CIO +3 dB (atrai usuários)
    - Carga alta (> 95%): CIO -4 dB (repele usuários)
    
    Args:
        bs_list: Lista de BSs
    """
    for bs in bs_list:
        bs.cio_db = choose_cio_from_load(bs.load())


def ric_update(bs_list, current_time):
    """Coordena atualização de todos os xApps do RIC.
    
    Executa em período definido (RIC_CONTROL_PERIOD = 10s):
    1. MRO: otimiza mobilidade
    2. MLB: balanceia carga
    
    Args:
        bs_list: Lista de BSs
        current_time: Tempo atual
    """
    ric_mro_update(bs_list, current_time)
    ric_mlb_update(bs_list)


# ============================================================
# SIMULAÇÃO PRINCIPAL
# ============================================================
# Implementa o loop principal de simulação:
#
# Processo em cada passo de tempo (50ms):
# 1. Atualiza parâmetros do RIC (a cada 10s)
# 2. Para cada usuário:
#    a. Atualiza posição (mobilidade)
#    b. Se conectado:
#       - Incrementa tempo conectado
#       - Verifica fim de conexão
#       - Verifica RLF
#       - Executa lógica de handover A3
#    c. Se desconectado:
#       - Tenta estabelecer conexão
#       - Conta tentativas bloqueadas
# 3. Coleta métricas:
#    - Carga média e máxima das BSs
#    - Usuários conectados
#    - Handovers, ping-pongs, RLFs
#    - Tentativas bloqueadas
#
# Retorna:
# - bs_list: lista de estações base
# - users: lista de usuários
# - poly: polígono da área
# - results: dicionário com métricas

def run_simulation():
    """Executa a simulação completa da rede celular.
    
    Returns:
        Tupla (bs_list, users, poly, results)
    """
    # Inicializa rede
    bs_list = generate_19_bs_hex_grid()
    poly = simulation_polygon()
    users = create_users(poly)

    # Listas para histórico de métricas
    time_history = []
    avg_load_history = []
    max_load_history = []
    connected_users_history = []
    handover_history = []
    pingpong_history = []
    rlf_history = []
    blocked_attempts_history = []

    # Contadores acumulados
    total_blocked_attempts = 0
    last_total_ho = 0
    last_total_pp = 0
    last_total_rlf = 0

    # Próxima atualização do RIC
    next_ric_time = 0.0

    # Loop principal de simulação
    for step in range(STEPS):
        current_time = step * DT

        # Atualiza parâmetros do RIC a cada 10 segundos
        if current_time >= next_ric_time:
            ric_update(bs_list, current_time)
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
                if check_rlf(ue, bs_list, current_time):
                    continue

                # Executa lógica de handover
                a3_handover_logic(ue, bs_list, current_time, DT)

            else:
                # Usuário desconectado: tenta conectar
                if current_time >= ue.next_attempt_time:
                    established = try_establish_connection(ue, bs_list, current_time)

                    if not established:
                        total_blocked_attempts += 1
                        blocked_this_step += 1
                        ue.next_attempt_time = generate_next_attempt_time(current_time)

        # Coleta métricas globais
        total_ho = sum(ue.total_handovers for ue in users)
        total_pp = sum(ue.total_pingpongs for ue in users)
        total_rlf = sum(ue.total_rlfs for ue in users)

        loads = [bs.load() for bs in bs_list]
        connected_users = sum(1 for ue in users if ue.connected)

        # Registra no histórico
        time_history.append(current_time)
        avg_load_history.append(np.mean(loads))
        max_load_history.append(np.max(loads))
        connected_users_history.append(connected_users)

        handover_history.append(total_ho - last_total_ho)
        pingpong_history.append(total_pp - last_total_pp)
        rlf_history.append(total_rlf - last_total_rlf)
        blocked_attempts_history.append(blocked_this_step)

        # Atualiza contadores
        last_total_ho = total_ho
        last_total_pp = total_pp
        last_total_rlf = total_rlf

    # Compila resultados
    results = {
        "time": np.array(time_history),
        "avg_load": np.array(avg_load_history),
        "max_load": np.array(max_load_history),
        "connected_users": np.array(connected_users_history),
        "handovers": np.array(handover_history),
        "pingpongs": np.array(pingpong_history),
        "rlfs": np.array(rlf_history),
        "blocked_attempts": np.array(blocked_attempts_history),
        "total_blocked_attempts": total_blocked_attempts,
    }

    return bs_list, users, poly, results


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
    # Calcula totais
    total_ho = sum(ue.total_handovers for ue in users)
    total_pp = sum(ue.total_pingpongs for ue in users)
    total_rlf = sum(ue.total_rlfs for ue in users)

    connected_final = sum(1 for ue in users if ue.connected)

    # Imprime resultados gerais
    print("\n================ RESULTADOS GERAIS ================")
    print(f"Tempo simulado: {SIM_TIME:.1f} s")
    print(f"Base stations: {len(bs_list)}")
    print(f"Usuários: {len(users)}")
    print(f"PRBs por BS: {TOTAL_PRBS_PER_BS}")
    print(f"Usuários conectados no fim: {connected_final}")
    print(f"Total de handovers: {total_ho}")
    print(f"Total de ping-pongs: {total_pp}")
    print(f"Total de RLFs: {total_rlf}")
    print(f"Tentativas bloqueadas: {results['total_blocked_attempts']}")

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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulação O-RAN com opção GPU")
    parser.add_argument("--gpu", action="store_true", help="Usar GPU via CuPy")
    parser.add_argument("--no-plots", action="store_true", help="Não gerar gráficos")
    args = parser.parse_args()

    try:
        set_backend(args.gpu)
    except ImportError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        sys.exit(1)

    print("Modo de execução:", "GPU (CuPy)" if args.gpu else "CPU (NumPy)")

    # Executa a simulação
    bs_list, users, poly, results = run_simulation()

    # Imprime resumo dos resultados
    print_summary(bs_list, users, results)

    # Gera visualizações
    if not args.no_plots:
        plot_topology(bs_list, users, poly)
        plot_results(results)
