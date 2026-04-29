import numpy as np
import matplotlib.pyplot as plt
from dataclasses import dataclass, field
from collections import deque, defaultdict

# ============================================================
# CONFIGURAÇÃO GERAL
# ============================================================

np.random.seed(42)

N_BS = 19
USERS_PER_BS = 20
N_USERS = N_BS * USERS_PER_BS

INTER_SITE_DISTANCE = 600.0

SIM_TIME = 1000.0
DT = 0.05
STEPS = int(SIM_TIME / DT)

# ============================================================
# PARÂMETROS DAS BASE STATIONS
# ============================================================

BS_TX_POWER_DBM = 28.0
BS_ANTENNA_GAIN_DB = 2.0
BS_HEIGHT_M = 10.0
BS_CABLE_LOSS_DB = 2.0

CENTER_FREQ_GHZ = 2.1
BANDWIDTH_HZ = 20e6
SUBCARRIER_COUNT = 12
SUBCARRIER_SPACING_HZ = 15e3

DEFAULT_CIO_DB = 0.0
DEFAULT_TTT_S = 0.064
DEFAULT_HYSTERESIS_DB = 0.0

# ============================================================
# PARÂMETROS DOS USUÁRIOS
# ============================================================

UE_ANTENNA_GAIN_DB = 0.0
UE_HEIGHT_M = 1.6
UE_CABLE_LOSS_DB = 0.0
UE_RX_SENSITIVITY_DBM = -80.0

PEDESTRIAN_SPEED = 5.0
VEHICLE_SPEED = 25.0
DIRECTION_CHANGE_PROB = 0.0006

# ============================================================
# PERFIS DE USUÁRIO
# ============================================================

USER_PROFILES = {
    "low": {
        "bitrate_bps": 96e3,
        "prob": 0.60,
        "color": "green"
    },
    "medium": {
        "bitrate_bps": 5e6,
        "prob": 0.30,
        "color": "olive"
    },
    "high": {
        "bitrate_bps": 24e6,
        "prob": 0.10,
        "color": "darkred"
    }
}

# ============================================================
# TRÁFEGO
# ============================================================

CONNECTION_ATTEMPT_MEAN = 20.0
CONNECTION_ATTEMPT_STD = 3.0

CONNECTION_DURATION_MEAN = 60.0
CONNECTION_DURATION_STD = 15.0

# ============================================================
# MODELO DE PROPAGAÇÃO
# ============================================================

BODY_LOSS_DB = 1.0
SLOW_FADING_MARGIN_DB = 4.0
FOLIAGE_LOSS_DB = 4.0
INTERFERENCE_MARGIN_DB = 2.0
RAIN_MARGIN_DB = 0.0

NOISE_FIGURE_DB = 7.0
THERMAL_NOISE_DBM_HZ = -174.0

# ============================================================
# PRB
# ============================================================

PRB_BANDWIDTH_HZ = 180e3
TOTAL_PRBS_PER_BS = int(BANDWIDTH_HZ / PRB_BANDWIDTH_HZ)

# ============================================================
# RIC / xApps
# ============================================================

RIC_CONTROL_PERIOD = 10.0
MRO_WINDOW = 240.0
PINGPONG_PERIOD = 10.0

RLF_SINR_THRESHOLD_DB = -6.0
RLF_RSRP_THRESHOLD_DBM = -110.0

# ============================================================
# TABELAS SIMPLES DE DECISÃO DOS xApps
# ============================================================

def choose_ttt_from_pingpong_ratio(ratio):
    if ratio < 0.05:
        return 0.064
    elif ratio < 0.15:
        return 0.128
    elif ratio < 0.30:
        return 0.256
    else:
        return 0.512


def choose_hysteresis_from_rlf_ratio(ratio):
    if ratio < 0.03:
        return 0.0
    elif ratio < 0.08:
        return 1.0
    elif ratio < 0.15:
        return 2.0
    else:
        return 3.0


def choose_cio_from_load(load):
    if load < 0.35:
        return 3.0
    elif load < 0.60:
        return 1.0
    elif load < 0.80:
        return 0.0
    elif load < 0.95:
        return -2.0
    else:
        return -4.0


# ============================================================
# CLASSES
# ============================================================

@dataclass
class BaseStation:
    bs_id: int
    x: float
    y: float

    tx_power_dbm: float = BS_TX_POWER_DBM
    antenna_gain_db: float = BS_ANTENNA_GAIN_DB
    height_m: float = BS_HEIGHT_M
    cable_loss_db: float = BS_CABLE_LOSS_DB

    cio_db: float = DEFAULT_CIO_DB
    ttt_s: float = DEFAULT_TTT_S
    hysteresis_db: float = DEFAULT_HYSTERESIS_DB

    used_prbs: int = 0

    ho_events: deque = field(default_factory=deque)
    pingpong_events: deque = field(default_factory=deque)
    rlf_events: deque = field(default_factory=deque)

    def load(self):
        return self.used_prbs / TOTAL_PRBS_PER_BS


@dataclass
class User:
    ue_id: int
    x: float
    y: float
    speed: float
    direction: float
    profile_name: str
    bitrate_bps: float
    color: str

    serving_bs: int = None
    connected: bool = False
    allocated_prbs: int = 0

    next_attempt_time: float = 0.0
    connection_end_time: float = 0.0

    candidate_bs: int = None
    ttt_timer: float = 0.0

    last_handover_time: float = -9999.0
    last_bs_before_ho: int = None

    total_handovers: int = 0
    total_pingpongs: int = 0
    total_rlfs: int = 0
    total_connected_time: float = 0.0


# ============================================================
# GEOMETRIA
# ============================================================

def generate_19_bs_hex_grid(isd=600, center_x=1000, center_y=1000):
    coords = []

    rings = 2
    for q in range(-rings, rings + 1):
        for r in range(-rings, rings + 1):
            s = -q - r
            if max(abs(q), abs(r), abs(s)) <= rings:
                x = center_x + isd * np.sqrt(3) * (q + r / 2)
                y = center_y + isd * 1.5 * r
                coords.append((x, y))

    coords = sorted(coords, key=lambda p: (p[1], p[0]))
    return [BaseStation(i + 1, x, y) for i, (x, y) in enumerate(coords)]


def simulation_polygon():
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
    inside = False
    j = len(poly) - 1

    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]

        intersect = ((yi > y) != (yj > y)) and \
            (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi)

        if intersect:
            inside = not inside

        j = i

    return inside


def random_point_inside(poly):
    min_x, min_y = poly.min(axis=0)
    max_x, max_y = poly.max(axis=0)

    while True:
        x = np.random.uniform(min_x, max_x)
        y = np.random.uniform(min_y, max_y)

        if point_inside_polygon(x, y, poly):
            return x, y


# ============================================================
# PROPAGAÇÃO 3GPP-STYLE UMa
# ============================================================

def dbm_to_mw(dbm):
    return 10 ** (dbm / 10)


def mw_to_dbm(mw):
    return 10 * np.log10(mw + 1e-30)


def distance_2d(bs, ue):
    return np.sqrt((bs.x - ue.x) ** 2 + (bs.y - ue.y) ** 2)


def distance_3d(bs, ue):
    d2d = distance_2d(bs, ue)
    return np.sqrt(d2d ** 2 + (bs.height_m - UE_HEIGHT_M) ** 2)


def pathloss_uma_nlos_38901(d3d_m, fc_ghz=CENTER_FREQ_GHZ):
    d3d_m = max(d3d_m, 10.0)

    pl = (
        13.54
        + 39.08 * np.log10(d3d_m)
        + 20.0 * np.log10(fc_ghz)
        - 0.6 * (UE_HEIGHT_M - 1.5)
    )

    return pl


def total_extra_losses_db():
    return (
        BODY_LOSS_DB
        + SLOW_FADING_MARGIN_DB
        + FOLIAGE_LOSS_DB
        + INTERFERENCE_MARGIN_DB
        + RAIN_MARGIN_DB
    )


def rx_power_dbm(bs, ue):
    d3d = distance_3d(bs, ue)
    pl = pathloss_uma_nlos_38901(d3d)

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
    return THERMAL_NOISE_DBM_HZ + 10 * np.log10(BANDWIDTH_HZ) + NOISE_FIGURE_DB


def calculate_sinr_db(ue, bs_list, serving_bs_index):
    rx_powers_dbm = np.array([rx_power_dbm(bs, ue) for bs in bs_list])

    signal_mw = dbm_to_mw(rx_powers_dbm[serving_bs_index])
    interference_mw = np.sum(dbm_to_mw(rx_powers_dbm)) - signal_mw
    noise_mw = dbm_to_mw(noise_power_dbm())

    sinr = signal_mw / (interference_mw + noise_mw)

    return 10 * np.log10(sinr + 1e-30), rx_powers_dbm


def spectral_efficiency_from_sinr(sinr_db):
    sinr_linear = 10 ** (sinr_db / 10)

    se = np.log2(1 + sinr_linear)

    return min(se, 6.0)


def required_prbs_for_user(ue, sinr_db):
    se = spectral_efficiency_from_sinr(sinr_db)
    capacity_per_prb = PRB_BANDWIDTH_HZ * se

    if capacity_per_prb <= 1:
        return TOTAL_PRBS_PER_BS + 1

    return int(np.ceil(ue.bitrate_bps / capacity_per_prb))


# ============================================================
# CRIAÇÃO DOS USUÁRIOS
# ============================================================

def sample_profile():
    names = list(USER_PROFILES.keys())
    probs = [USER_PROFILES[n]["prob"] for n in names]
    selected = np.random.choice(names, p=probs)

    profile = USER_PROFILES[selected]

    return selected, profile["bitrate_bps"], profile["color"]


def normal_positive(mean, std, min_value=0.1):
    value = np.random.normal(mean, std)
    return max(value, min_value)


def generate_next_attempt_time(current_time):
    return current_time + normal_positive(
        CONNECTION_ATTEMPT_MEAN,
        CONNECTION_ATTEMPT_STD,
        min_value=1.0
    )


def generate_connection_duration():
    return normal_positive(
        CONNECTION_DURATION_MEAN,
        CONNECTION_DURATION_STD,
        min_value=1.0
    )


def create_users(poly):
    users = []

    for i in range(N_USERS):
        x, y = random_point_inside(poly)

        is_pedestrian = np.random.rand() < 0.80
        speed = PEDESTRIAN_SPEED if is_pedestrian else VEHICLE_SPEED
        direction = np.random.uniform(0, 2 * np.pi)

        profile_name, bitrate, color = sample_profile()

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

        ue.next_attempt_time = generate_next_attempt_time(0.0)

        users.append(ue)

    return users


# ============================================================
# ASSOCIAÇÃO E HANDOVER
# ============================================================

def best_bs_by_rsrp(ue, bs_list):
    rsrp = np.array([
        rx_power_dbm_no_fast_random(bs, ue) + bs.cio_db
        for bs in bs_list
    ])

    best_index = int(np.argmax(rsrp))

    return best_index, rsrp


def nearest_or_best_bs_initial(ue, bs_list):
    best_index, _ = best_bs_by_rsrp(ue, bs_list)
    return best_index


def release_connection(ue, bs_list):
    if ue.connected and ue.serving_bs is not None:
        bs_list[ue.serving_bs].used_prbs -= ue.allocated_prbs
        bs_list[ue.serving_bs].used_prbs = max(0, bs_list[ue.serving_bs].used_prbs)

    ue.connected = False
    ue.allocated_prbs = 0
    ue.serving_bs = None
    ue.candidate_bs = None
    ue.ttt_timer = 0.0


def try_establish_connection(ue, bs_list, current_time):
    candidate_order = []

    rsrp = np.array([
        rx_power_dbm_no_fast_random(bs, ue) + bs.cio_db
        for bs in bs_list
    ])

    candidate_order = list(np.argsort(rsrp)[::-1])

    for bs_idx in candidate_order:
        bs = bs_list[bs_idx]

        sinr_db, rx_powers = calculate_sinr_db(ue, bs_list, bs_idx)

        if rx_powers[bs_idx] < UE_RX_SENSITIVITY_DBM:
            continue

        prbs = required_prbs_for_user(ue, sinr_db)

        if bs.used_prbs + prbs <= TOTAL_PRBS_PER_BS:
            bs.used_prbs += prbs

            ue.connected = True
            ue.serving_bs = bs_idx
            ue.allocated_prbs = prbs
            ue.connection_end_time = current_time + generate_connection_duration()

            return True

    return False


def perform_handover(ue, bs_list, target_bs_idx, current_time):
    source_bs_idx = ue.serving_bs

    source_bs = bs_list[source_bs_idx]
    target_bs = bs_list[target_bs_idx]

    sinr_db, rx_powers = calculate_sinr_db(ue, bs_list, target_bs_idx)

    if rx_powers[target_bs_idx] < UE_RX_SENSITIVITY_DBM:
        return False

    required_prbs = required_prbs_for_user(ue, sinr_db)

    if target_bs.used_prbs + required_prbs > TOTAL_PRBS_PER_BS:
        return False

    source_bs.used_prbs -= ue.allocated_prbs
    source_bs.used_prbs = max(0, source_bs.used_prbs)

    target_bs.used_prbs += required_prbs

    ue.last_bs_before_ho = source_bs_idx
    old_last_ho_time = ue.last_handover_time

    ue.serving_bs = target_bs_idx
    ue.allocated_prbs = required_prbs
    ue.total_handovers += 1
    ue.last_handover_time = current_time

    source_bs.ho_events.append(current_time)

    if (
        old_last_ho_time > 0
        and current_time - old_last_ho_time <= PINGPONG_PERIOD
        and target_bs_idx == ue.last_bs_before_ho
    ):
        ue.total_pingpongs += 1
        source_bs.pingpong_events.append(current_time)

    return True


def a3_handover_logic(ue, bs_list, current_time, dt):
    if not ue.connected:
        return

    current_idx = ue.serving_bs
    current_bs = bs_list[current_idx]

    best_idx, rsrp = best_bs_by_rsrp(ue, bs_list)

    if best_idx == current_idx:
        ue.candidate_bs = None
        ue.ttt_timer = 0.0
        return

    current_rsrp = rsrp[current_idx]
    target_rsrp = rsrp[best_idx]

    a3_condition = target_rsrp > current_rsrp + current_bs.hysteresis_db

    if a3_condition:
        if ue.candidate_bs == best_idx:
            ue.ttt_timer += dt
        else:
            ue.candidate_bs = best_idx
            ue.ttt_timer = dt

        if ue.ttt_timer >= current_bs.ttt_s:
            perform_handover(ue, bs_list, best_idx, current_time)
            ue.candidate_bs = None
            ue.ttt_timer = 0.0
    else:
        ue.candidate_bs = None
        ue.ttt_timer = 0.0


# ============================================================
# MOBILIDADE
# ============================================================

def update_user_position(ue, poly):
    if np.random.rand() < DIRECTION_CHANGE_PROB:
        ue.direction = np.random.uniform(0, 2 * np.pi)

    old_x, old_y = ue.x, ue.y

    ue.x += ue.speed * np.cos(ue.direction) * DT
    ue.y += ue.speed * np.sin(ue.direction) * DT

    if not point_inside_polygon(ue.x, ue.y, poly):
        ue.x, ue.y = old_x, old_y
        ue.direction = np.random.uniform(0, 2 * np.pi)


# ============================================================
# RLF
# ============================================================

def check_rlf(ue, bs_list, current_time):
    if not ue.connected:
        return False

    sinr_db, rx_powers = calculate_sinr_db(ue, bs_list, ue.serving_bs)
    rsrp = rx_powers[ue.serving_bs]

    if sinr_db < RLF_SINR_THRESHOLD_DB or rsrp < RLF_RSRP_THRESHOLD_DBM:
        bs_list[ue.serving_bs].rlf_events.append(current_time)
        ue.total_rlfs += 1

        release_connection(ue, bs_list)
        ue.next_attempt_time = generate_next_attempt_time(current_time)

        return True

    return False


# ============================================================
# nRT-RIC / xApps
# ============================================================

def cleanup_old_events(bs_list, current_time):
    min_time = current_time - MRO_WINDOW

    for bs in bs_list:
        while bs.ho_events and bs.ho_events[0] < min_time:
            bs.ho_events.popleft()

        while bs.pingpong_events and bs.pingpong_events[0] < min_time:
            bs.pingpong_events.popleft()

        while bs.rlf_events and bs.rlf_events[0] < min_time:
            bs.rlf_events.popleft()


def ric_mro_update(bs_list, current_time):
    cleanup_old_events(bs_list, current_time)

    for bs in bs_list:
        total_ho = len(bs.ho_events)
        total_pp = len(bs.pingpong_events)
        total_rlf = len(bs.rlf_events)

        pp_ratio = total_pp / total_ho if total_ho > 0 else 0.0
        rlf_ratio = total_rlf / total_ho if total_ho > 0 else 0.0

        bs.ttt_s = choose_ttt_from_pingpong_ratio(pp_ratio)
        bs.hysteresis_db = choose_hysteresis_from_rlf_ratio(rlf_ratio)


def ric_mlb_update(bs_list):
    for bs in bs_list:
        bs.cio_db = choose_cio_from_load(bs.load())


def ric_update(bs_list, current_time):
    ric_mro_update(bs_list, current_time)
    ric_mlb_update(bs_list)


# ============================================================
# SIMULAÇÃO
# ============================================================

def run_simulation():
    bs_list = generate_19_bs_hex_grid()
    poly = simulation_polygon()
    users = create_users(poly)

    time_history = []
    avg_load_history = []
    max_load_history = []
    connected_users_history = []
    handover_history = []
    pingpong_history = []
    rlf_history = []
    blocked_attempts_history = []

    total_blocked_attempts = 0
    last_total_ho = 0
    last_total_pp = 0
    last_total_rlf = 0

    next_ric_time = 0.0

    for step in range(STEPS):
        current_time = step * DT

        if current_time >= next_ric_time:
            ric_update(bs_list, current_time)
            next_ric_time += RIC_CONTROL_PERIOD

        blocked_this_step = 0

        for ue in users:
            update_user_position(ue, poly)

            if ue.connected:
                ue.total_connected_time += DT

                if current_time >= ue.connection_end_time:
                    release_connection(ue, bs_list)
                    ue.next_attempt_time = generate_next_attempt_time(current_time)
                    continue

                if check_rlf(ue, bs_list, current_time):
                    continue

                a3_handover_logic(ue, bs_list, current_time, DT)

            else:
                if current_time >= ue.next_attempt_time:
                    established = try_establish_connection(ue, bs_list, current_time)

                    if not established:
                        total_blocked_attempts += 1
                        blocked_this_step += 1
                        ue.next_attempt_time = generate_next_attempt_time(current_time)

        total_ho = sum(ue.total_handovers for ue in users)
        total_pp = sum(ue.total_pingpongs for ue in users)
        total_rlf = sum(ue.total_rlfs for ue in users)

        loads = [bs.load() for bs in bs_list]
        connected_users = sum(1 for ue in users if ue.connected)

        time_history.append(current_time)
        avg_load_history.append(np.mean(loads))
        max_load_history.append(np.max(loads))
        connected_users_history.append(connected_users)

        handover_history.append(total_ho - last_total_ho)
        pingpong_history.append(total_pp - last_total_pp)
        rlf_history.append(total_rlf - last_total_rlf)
        blocked_attempts_history.append(blocked_this_step)

        last_total_ho = total_ho
        last_total_pp = total_pp
        last_total_rlf = total_rlf

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
# PLOTS
# ============================================================

def plot_topology(bs_list, users, poly):
    plt.figure(figsize=(8, 8))

    closed_poly = np.vstack([poly, poly[0]])
    plt.plot(closed_poly[:, 0], closed_poly[:, 1], color="black", linewidth=2)

    for bs in bs_list:
        plt.scatter(bs.x, bs.y, marker="1", s=120, color="blue")
        plt.text(bs.x + 40, bs.y + 40, str(bs.bs_id), color="blue", fontsize=10)

    for ue in users:
        plt.scatter(ue.x, ue.y, s=14, color=ue.color)

    plt.xlabel("x")
    plt.ylabel("y")
    plt.title("Simulation area, 19 base stations and 380 users")
    plt.grid(True)
    plt.axis("equal")
    plt.show()


def plot_results(results):
    t = results["time"]

    plt.figure(figsize=(9, 4))
    plt.plot(t, results["connected_users"])
    plt.xlabel("Tempo [s]")
    plt.ylabel("Usuários conectados")
    plt.title("Usuários conectados ao longo do tempo")
    plt.grid(True)
    plt.show()

    plt.figure(figsize=(9, 4))
    plt.plot(t, results["avg_load"], label="Carga média")
    plt.plot(t, results["max_load"], label="Carga máxima")
    plt.xlabel("Tempo [s]")
    plt.ylabel("Carga PRB")
    plt.title("Carga das base stations")
    plt.legend()
    plt.grid(True)
    plt.show()

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

    plt.figure(figsize=(9, 4))
    plt.plot(t, np.cumsum(results["blocked_attempts"]))
    plt.xlabel("Tempo [s]")
    plt.ylabel("Tentativas bloqueadas acumuladas")
    plt.title("Bloqueios por falta de PRB")
    plt.grid(True)
    plt.show()


def print_summary(bs_list, users, results):
    total_ho = sum(ue.total_handovers for ue in users)
    total_pp = sum(ue.total_pingpongs for ue in users)
    total_rlf = sum(ue.total_rlfs for ue in users)

    connected_final = sum(1 for ue in users if ue.connected)

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

    if total_ho > 0:
        print(f"Razão ping-pong / handover: {total_pp / total_ho:.3f}")
        print(f"Razão RLF / handover: {total_rlf / total_ho:.3f}")

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
# MAIN
# ============================================================

if __name__ == "__main__":
    bs_list, users, poly, results = run_simulation()

    print_summary(bs_list, users, results)

    plot_topology(bs_list, users, poly)
    plot_results(results)
