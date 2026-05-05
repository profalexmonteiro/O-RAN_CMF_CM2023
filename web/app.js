const stateUrl = "/api/state";
const startUrl = "/api/start";
const stopUrl = "/api/stop";
let pollingTimer = null;
let simulationRunning = false;
let simulationRequestPending = false;
let setupPreviewActive = false;
let currentLanguage = "pt";
const ANTENNA_DISPLAY_ORIGIN = 1500;

const i18n = {
    pt: {
        htmlLang: "pt-BR",
        documentTitle: "Simulação O-RAN - Interface Web",
        languageButton: "English",
        startButton: "Iniciar Simulação",
        stopButton: "Parar Simulação",
        expandCard: "Abrir",
        collapseCard: "Fechar",
        statusFallback: "Aguardando início.",
        startedMessage: "Simulação iniciada.",
        stoppingMessage: "Solicitada parada.",
        startError: "Erro ao iniciar simulação.",
        fetchError: "Falha ao buscar estado",
        texts: {
            "header h1": "Simulação O-RAN",
            "header p": "Interface web com aba de setup e visualização em tempo real.",
            "#tab-setup": "Setup",
            "#tab-visual": "Visualização",
            "#setup-panel > h2": "Configuração da Simulação",
            ".setup-form-header h3": "Cenário Essencial",
            ".setup-form-header p": "Ajuste apenas estes campos para rodar um cenário básico. Os demais cartões refinam rádio, mobilidade e controle.",
            "#setup-visual-shortcut": "Ir para Visualização",
            "#setup-panel .parameter-card:nth-of-type(1) h3": "Estações Base",
            "#setup-panel .parameter-card:nth-of-type(2) h3": "Usuários",
            "#setup-panel .parameter-card:nth-of-type(3) h3": "Perfis de Usuário",
            "#setup-panel .parameter-card:nth-of-type(3) .card-description": "Cada perfil define o bitrate exigido pelo usuário e a probabilidade de atribuição aleatória desse perfil.",
            "#setup-panel .parameter-card:nth-of-type(4) h3": "Generação de Tráfego",
            "#setup-panel .parameter-card:nth-of-type(4) .card-description": "Cada usuário gera tráfego por tentativas de conexão. A conexão só é estabelecida quando alguma estação base possui PRBs livres suficientes, e pode sofrer handover após evento A3.",
            "#setup-panel .parameter-card:nth-of-type(5) h3": "Modelo de Propagação",
            "#setup-panel .parameter-card:nth-of-type(5) .card-description": "O modelo UMa (Urban Macro) do 3GPP TR 38.901 é utilizado para calcular pathloss e margens adicionais de propagação.",
            "#setup-panel .parameter-card:nth-of-type(6) h3": "Configuração do RIC",
            "#setup-panel .parameter-card:nth-of-type(6) .card-description": "Todas as estações base são gerenciadas por um único near-RT RIC. Os xApps MRO e MLB são executados simultaneamente para ajustar handover e balanceamento de carga.",
            "#setup-start-button": "Iniciar Simulação",
            "#visual-panel .visual-header h2": "Visualização em Tempo Real",
            "#visual-panel .visual-header p": "Monitore os movimentos das antenas e dos UEs.",
            "#visual-panel .metrics p:nth-child(1) strong": "Conectados:",
            "#visual-panel .metrics p:nth-child(2) strong": "Satisfação:",
            "#visual-panel .metrics p:nth-child(3) strong": "Handovers:",
            "#visual-panel .metrics p:nth-child(4) strong": "Ping-pong:",
            "#visual-panel .metrics p:nth-child(5) strong": "RLFs:",
            "#visual-panel .metrics p:nth-child(6) strong": "Call blockages:",
            "#visual-panel .metrics p:nth-child(7) strong": "Load médio:",
            "#visual-panel .metrics p:nth-child(8) strong": "Load máximo:",
            "#visual-panel .metrics p:nth-child(9) strong": "Antenas:",
            ".visual-status h3": "Status",
            ".visual-status p:nth-child(3) strong": "Última atualização:",
            ".visual-status p:nth-child(4) strong": "Progresso:",
            ".legend span:nth-child(1)": "Low bitrate: 96 kbps (60%)",
            ".legend span:nth-child(2)": "Medium bitrate: 5000 kbps (30%)",
            ".legend span:nth-child(3)": "High bitrate: 24000 kbps (10%)",
            ".legend span:nth-child(4)": "Antena (BS)",
        },
        labels: {
            scenario_preset: "Preset de cenário",
            sim_time: "Tempo de simulação (s)",
            inter_site_distance: "Distância entre antenas (m)",
            n_bs: "Quantidade de antenas",
            cmf_mode: "Tipo de simulação",
            export_bs_results: "Gerar CSVs por estação base",
            bs_antenna_gain_db: "Ganho da antena (dB)",
            bs_height_m: "Altura da antena (m)",
            bs_cable_loss_db: "Perda no cabo (dB)",
            bs_tx_power_dbm: "Potência TX (dBm)",
            center_freq_mhz: "Frequência central (MHz)",
            bandwidth_mhz: "Bandwidth (MHz)",
            subcarrier_count: "Subcarrier count",
            subcarrier_spacing_khz: "Subcarrier spacing (kHz)",
            default_cio_db: "Cell Individual Offset padrão (dB)",
            default_ttt_s: "Handover Time-To-Trigger padrão (s)",
            default_hysteresis_db: "Histerese de handover padrão (dB)",
            ue_rx_sensitivity_dbm: "Sensibilidade RX (dBm)",
            ue_rx_sensitivity_margin_db: "Margem de sensibilidade RX (dB)",
            n_users: "Número de UEs",
            users_per_bs: "Usuários por estação base",
            dt: "Atualização de posição (s)",
            pedestrian_prob_pct: "Pedestres (%)",
            pedestrian_speed: "Velocidade pedestre (m/s)",
            vehicle_speed: "Velocidade veículo (m/s)",
            direction_change_prob_pct: "Mudança de direção (%)",
            ue_antenna_gain_db: "Ganho da antena UE (dB)",
            ue_height_m: "Altura da antena UE (m)",
            ue_cable_loss_db: "Perda no cabo UE (dB)",
            ue_mimo_layers: "MIMO layers",
            low_bitrate_kbps: "Low bitrate (kbps)",
            low_profile_prob_pct: "Low profile (%)",
            medium_bitrate_kbps: "Medium bitrate (kbps)",
            medium_profile_prob_pct: "Medium profile (%)",
            high_bitrate_kbps: "High bitrate (kbps)",
            high_profile_prob_pct: "High profile (%)",
            connection_attempt_mean: "Média entre tentativas (s)",
            connection_attempt_std: "Desvio entre tentativas (s)",
            connection_duration_mean: "Duração média da conexão (s)",
            connection_duration_std: "Desvio da duração (s)",
            body_loss_db: "Body loss (dB)",
            slow_fading_margin_db: "Slow-fading margin (dB)",
            foliage_loss_db: "Foliage loss (dB)",
            interference_margin_db: "Interference margin (dB)",
            rain_margin_db: "Rain margin (dB)",
            ric_control_period: "Período de controle RIC (s)",
            mro_window: "Janela MRO (s)",
            pingpong_period: "Período ping-pong (s)",
        },
        tooltips: {
            sim_time: "Tempo total que a simulação executa, em segundos.",
            inter_site_distance: "Distância entre estações base no grid hexagonal. Esse valor altera o espaçamento visual e físico entre as antenas.",
            n_bs: "Quantidade de antenas/estações base geradas no grid hexagonal da simulação.",
            cmf_mode: "Modo do Conflict Mitigation Framework usado para resolver prioridades entre otimização de mobilidade e balanceamento de carga.",
            export_bs_results: "Quando habilitado, a simulação gera um arquivo CSV por estação base em simulation_results/<tipo_de_simulacao>.",
            bs_antenna_gain_db: "Ganho aplicado pela antena da estação base ao sinal transmitido. Valores maiores aumentam a potência efetiva irradiada e podem melhorar o RSRP recebido pelos UEs.",
            bs_height_m: "Altura física da antena da estação base em relação ao solo. Afeta o modelo de propagação e a distância de cobertura, especialmente em cenários macro urbanos.",
            bs_cable_loss_db: "Perda de potência causada por cabos, conectores e elementos RF entre o transmissor e a antena. Esse valor reduz a potência efetiva transmitida.",
            bs_tx_power_dbm: "Potência de transmissão da estação base em dBm. É a potência inicial usada no cálculo de enlace antes dos ganhos e perdas de antena, cabo e propagação.",
            center_freq_mhz: "Frequência central da portadora usada pela rede. Frequências maiores geralmente sofrem maior perda de percurso no modelo de propagação.",
            bandwidth_mhz: "Largura total de banda disponível para transmissão. Afeta o ruído térmico calculado e a quantidade de recursos de rádio disponíveis.",
            subcarrier_count: "Número de subportadoras considerado como referência na configuração de rádio. No modelo atual, é mantido como parâmetro de configuração da simulação.",
            subcarrier_spacing_khz: "Espaçamento entre subportadoras OFDM. O valor padrão de 15 kHz é típico em configurações LTE/5G numerology 0.",
            default_cio_db: "Offset individual da célula usado nas decisões de handover e balanceamento de carga. Valores positivos tornam a célula mais atrativa; valores negativos a tornam menos atrativa.",
            default_ttt_s: "Tempo mínimo pelo qual a condição de handover precisa permanecer válida antes da troca de célula ser executada. Valores maiores reduzem handovers rápidos, mas podem atrasar a reação.",
            default_hysteresis_db: "Margem adicional exigida para confirmar que uma célula vizinha está melhor que a célula atual. Ajuda a evitar handovers instáveis e eventos de ping-pong.",
            n_users: "Quantidade total de equipamentos de usuário distribuídos aleatoriamente dentro da área de simulação. O valor padrão é 380.",
            users_per_bs: "Quantidade nominal de usuários por estação base. Com 19 estações e 20 usuários por BS, o cenário padrão totaliza 380 usuários.",
            dt: "Passo de atualização da simulação. A cada 0.05 s, posições, conexões e eventos de mobilidade são reavaliados.",
            pedestrian_prob_pct: "Probabilidade de um usuário ser pedestre. O restante dos usuários é tratado como veículo. Valor padrão: 80%.",
            pedestrian_speed: "Velocidade constante dos usuários pedestres durante o movimento aleatório dentro da área.",
            vehicle_speed: "Velocidade constante dos usuários em veículos durante o movimento aleatório dentro da área.",
            direction_change_prob_pct: "Probabilidade de mudar a direção a cada atualização de posição. Se o usuário alcançar a fronteira da área, a direção é alterada com probabilidade de 100%.",
            ue_antenna_gain_db: "Ganho da antena do equipamento de usuário. Afeta a potência recebida no cálculo do enlace.",
            ue_height_m: "Altura média do equipamento de usuário em relação ao solo, usada no modelo de propagação.",
            ue_cable_loss_db: "Perda de cabo do equipamento de usuário. Em dispositivos móveis, normalmente é considerada desprezível.",
            ue_mimo_layers: "Número de camadas MIMO representando a configuração 2x2. No modelo atual, esse valor é armazenado como parâmetro do cenário.",
            scenario_preset: "Escolha um preset rápido para testar cenários comuns sem ajustar todos os parâmetros manualmente.",
            ue_rx_sensitivity_dbm: "Sensibilidade mínima de recepção do UE. Sinais abaixo desse limite não são aceitos para conexão ou handover.",
            ue_rx_sensitivity_margin_db: "Margem de tolerância aplicada ao check de sensibilidade. Use valores positivos para aceitar sinais mais fracos durante o handover.",
            low_bitrate_kbps: "Taxa de dados exigida pelos usuários do perfil low bitrate. Esse valor representa o throughput mínimo necessário para satisfazer o serviço do usuário. Cor no gráfico: verde.",
            low_profile_prob_pct: "Probabilidade de um UE receber aleatoriamente o perfil low bitrate ao ser criado. Valor padrão: 60%.",
            medium_bitrate_kbps: "Taxa de dados exigida pelos usuários do perfil medium bitrate. Esse valor representa o throughput mínimo necessário para satisfazer o serviço do usuário. Cor no gráfico: amarelo.",
            medium_profile_prob_pct: "Probabilidade de um UE receber aleatoriamente o perfil medium bitrate ao ser criado. Valor padrão: 30%.",
            high_bitrate_kbps: "Taxa de dados exigida pelos usuários do perfil high bitrate. Esse valor representa o throughput mínimo necessário para satisfazer o serviço do usuário. Cor no gráfico: vermelho.",
            high_profile_prob_pct: "Probabilidade de um UE receber aleatoriamente o perfil high bitrate ao ser criado. Valor padrão: 10%.",
            connection_attempt_mean: "Tempo médio entre tentativas de conexão geradas por cada usuário. O processo representa chegadas aleatórias de tráfego na rede.",
            connection_attempt_std: "Desvio padrão do tempo entre tentativas de conexão. Valores maiores tornam as chegadas de tráfego mais dispersas.",
            connection_duration_mean: "Duração média de uma conexão estabelecida. Durante esse período, o usuário mantém PRBs alocados na estação base servidora.",
            connection_duration_std: "Desvio padrão da duração da conexão. Valores maiores aumentam a variação do tempo em que conexões permanecem ativas.",
            body_loss_db: "Perda adicional causada pela absorção do corpo do usuário ou obstrução próxima ao terminal.",
            slow_fading_margin_db: "Margem usada para representar variações lentas do canal, como sombreamento por prédios e obstáculos.",
            foliage_loss_db: "Perda adicional associada à vegetação entre transmissor e receptor.",
            interference_margin_db: "Margem adicionada para representar interferência de outras células ou transmissões concorrentes.",
            rain_margin_db: "Margem de atenuação por chuva. No cenário padrão, a chuva não é considerada e o valor é 0 dB.",
            ric_control_period: "Período entre execuções do controle RIC. A cada ciclo, os xApps MRO e MLB reavaliam estatísticas, carga e parâmetros das estações base.",
            mro_window: "Janela histórica usada pelo MRO para calcular a razão de ping-pongs e RLFs em relação ao total de handovers recentes.",
            pingpong_period: "Intervalo máximo para classificar um handover BS #1 -> BS #2 -> BS #1 como ping-pong. Valor padrão: 10 segundos.",
        },
        options: {
            no_CM: "Sem CMF",
            prio_MRO: "Prioridade MRO",
            prio_MLB: "Prioridade MLB",
        },
    },
    en: {
        htmlLang: "en",
        documentTitle: "O-RAN Simulation - Web Interface",
        languageButton: "Português BR",
        startButton: "Start Simulation",
        stopButton: "Stop Simulation",
        expandCard: "Open",
        collapseCard: "Close",
        statusFallback: "Waiting to start.",
        startedMessage: "Simulation started.",
        stoppingMessage: "Stop requested.",
        startError: "Error starting simulation.",
        fetchError: "Failed to fetch state",
        texts: {
            "header h1": "O-RAN Simulation",
            "header p": "Web interface with setup and real-time visualization tabs.",
            "#tab-setup": "Setup",
            "#tab-visual": "Visualization",
            "#setup-panel > h2": "Simulation Setup",
            ".setup-form-header h3": "Essential Scenario",
            ".setup-form-header p": "Adjust only these fields to run a basic scenario. The remaining cards refine radio, mobility, and control behavior.",
            "#setup-visual-shortcut": "Go to Visualization",
            "#setup-panel .parameter-card:nth-of-type(1) h3": "Base Station Parameters",
            "#setup-panel .parameter-card:nth-of-type(2) h3": "Users",
            "#setup-panel .parameter-card:nth-of-type(3) h3": "User Profiles",
            "#setup-panel .parameter-card:nth-of-type(3) .card-description": "Each profile defines the user's demanded bitrate and the random assignment probability for that profile.",
            "#setup-panel .parameter-card:nth-of-type(4) h3": "Traffic Generation",
            "#setup-panel .parameter-card:nth-of-type(4) .card-description": "Each user generates traffic through connection attempts. A connection is established only when a base station has enough free PRBs, and it can be handed over after an A3 event.",
            "#setup-panel .parameter-card:nth-of-type(5) h3": "Propagation Model",
            "#setup-panel .parameter-card:nth-of-type(5) .card-description": "The 3GPP TR 38.901 UMa (Urban Macro) model is used to calculate pathloss and additional propagation margins.",
            "#setup-panel .parameter-card:nth-of-type(6) h3": "RIC Configuration",
            "#setup-start-button": "Start Simulation",
            "#setup-panel .parameter-card:nth-of-type(6) .card-description": "All base stations are managed by a single near-RT RIC. The MRO and MLB xApps run simultaneously to adjust handover and load balancing.",
            "#visual-panel .visual-header h2": "Real-Time Visualization",
            "#visual-panel .visual-header p": "Monitor antenna and UE movement.",
            "#visual-panel .metrics p:nth-child(1) strong": "Connected:",
            "#visual-panel .metrics p:nth-child(2) strong": "Satisfaction:",
            "#visual-panel .metrics p:nth-child(3) strong": "Handovers:",
            "#visual-panel .metrics p:nth-child(4) strong": "Ping-pong:",
            "#visual-panel .metrics p:nth-child(5) strong": "RLFs:",
            "#visual-panel .metrics p:nth-child(6) strong": "Call blockages:",
            "#visual-panel .metrics p:nth-child(7) strong": "Average load:",
            "#visual-panel .metrics p:nth-child(8) strong": "Max load:",
            "#visual-panel .metrics p:nth-child(9) strong": "Antennas:",
            ".visual-status h3": "Status",
            ".visual-status p:nth-child(3) strong": "Last update:",
            ".visual-status p:nth-child(4) strong": "Progress:",
            ".legend span:nth-child(1)": "Low bitrate: 96 kbps (60%)",
            ".legend span:nth-child(2)": "Medium bitrate: 5000 kbps (30%)",
            ".legend span:nth-child(3)": "High bitrate: 24000 kbps (10%)",
            ".legend span:nth-child(4)": "Antenna (BS)",
        },
        labels: {
            scenario_preset: "Scenario preset",
            sim_time: "Simulation time (s)",
            inter_site_distance: "Distance between antennas (m)",
            n_bs: "Number of antennas",
            cmf_mode: "Simulation type",
            export_bs_results: "Generate CSVs per base station",
            bs_antenna_gain_db: "Antenna gain (dB)",
            bs_height_m: "Antenna height (m)",
            bs_cable_loss_db: "Cable loss (dB)",
            bs_tx_power_dbm: "TX power (dBm)",
            center_freq_mhz: "Center frequency (MHz)",
            bandwidth_mhz: "Bandwidth (MHz)",
            subcarrier_count: "Subcarrier count",
            subcarrier_spacing_khz: "Subcarrier spacing (kHz)",
            default_cio_db: "Default Cell Individual Offset (dB)",
            default_ttt_s: "Default handover Time-To-Trigger (s)",
            default_hysteresis_db: "Default handover hysteresis (dB)",
            ue_rx_sensitivity_dbm: "RX sensitivity (dBm)",
            ue_rx_sensitivity_margin_db: "RX sensitivity margin (dB)",
            n_users: "Number of UEs",
            users_per_bs: "Users per base station",
            dt: "Position update interval (s)",
            pedestrian_prob_pct: "Pedestrians (%)",
            pedestrian_speed: "Pedestrian speed (m/s)",
            vehicle_speed: "Vehicle speed (m/s)",
            direction_change_prob_pct: "Direction change (%)",
            ue_antenna_gain_db: "UE antenna gain (dB)",
            ue_height_m: "UE antenna height (m)",
            ue_cable_loss_db: "UE cable loss (dB)",
            ue_mimo_layers: "MIMO layers",
            ue_rx_sensitivity_dbm: "RX sensitivity (dBm)",
            low_bitrate_kbps: "Low bitrate (kbps)",
            low_profile_prob_pct: "Low profile (%)",
            medium_bitrate_kbps: "Medium bitrate (kbps)",
            medium_profile_prob_pct: "Medium profile (%)",
            high_bitrate_kbps: "High bitrate (kbps)",
            high_profile_prob_pct: "High profile (%)",
            connection_attempt_mean: "Mean time between attempts (s)",
            connection_attempt_std: "Attempt interval std. dev. (s)",
            connection_duration_mean: "Mean connection duration (s)",
            connection_duration_std: "Connection duration std. dev. (s)",
            body_loss_db: "Body loss (dB)",
            slow_fading_margin_db: "Slow-fading margin (dB)",
            foliage_loss_db: "Foliage loss (dB)",
            interference_margin_db: "Interference margin (dB)",
            rain_margin_db: "Rain margin (dB)",
            ric_control_period: "RIC control period (s)",
            mro_window: "MRO window (s)",
            pingpong_period: "Ping-pong period (s)",
        },
        tooltips: {
            sim_time: "Total time the simulation runs, in seconds.",
            inter_site_distance: "Distance between base stations in the hexagonal grid. This value changes the visual and physical spacing between antennas.",
            n_bs: "Number of antennas/base stations generated in the simulation hexagonal grid.",
            cmf_mode: "Conflict Mitigation Framework mode used to prioritize mobility optimization or load balancing.",
            export_bs_results: "When enabled, the simulation generates one CSV file per base station under simulation_results/<simulation_type>.",
            bs_antenna_gain_db: "Gain applied by the base-station antenna to the transmitted signal. Higher values increase effective radiated power and may improve UE RSRP.",
            bs_height_m: "Physical height of the base-station antenna above ground. It affects the propagation model and coverage distance, especially in urban macro scenarios.",
            bs_cable_loss_db: "Power loss caused by cables, connectors, and RF components between the transmitter and the antenna. This reduces effective transmitted power.",
            bs_tx_power_dbm: "Base-station transmit power in dBm. This is the initial link-budget power before antenna, cable, and propagation gains or losses.",
            center_freq_mhz: "Carrier center frequency used by the network. Higher frequencies usually experience higher pathloss in the propagation model.",
            bandwidth_mhz: "Total bandwidth available for transmission. It affects calculated thermal noise and available radio resources.",
            subcarrier_count: "Number of subcarriers used as a radio-configuration reference. In the current model, it is kept as a simulation configuration parameter.",
            subcarrier_spacing_khz: "OFDM subcarrier spacing. The default 15 kHz value is typical for LTE/5G numerology 0.",
            default_cio_db: "Cell-specific offset used in handover and load-balancing decisions. Positive values make a cell more attractive; negative values make it less attractive.",
            default_ttt_s: "Minimum time for which the handover condition must remain valid before the handover is executed. Higher values reduce quick handovers but may delay reaction.",
            default_hysteresis_db: "Additional margin required to confirm that a neighboring cell is better than the current cell. It helps avoid unstable handovers and ping-pong events.",
            n_users: "Total number of user equipments randomly distributed across the simulation area. The default value is 380.",
            users_per_bs: "Nominal number of users per base station. With 19 stations and 20 users per BS, the default scenario has 380 users.",
            dt: "Simulation update step. Every 0.05 s, positions, connections, and mobility events are reevaluated.",
            pedestrian_prob_pct: "Probability that a user is a pedestrian. Remaining users are treated as vehicles. Default value: 80%.",
            pedestrian_speed: "Constant speed of pedestrian users during random movement inside the area.",
            vehicle_speed: "Constant speed of vehicle users during random movement inside the area.",
            direction_change_prob_pct: "Probability of changing movement direction at each position update. If the user reaches the area boundary, direction changes with 100% probability.",
            ue_antenna_gain_db: "Antenna gain of the user equipment. It affects received power in the link calculation.",
            ue_height_m: "Average user-equipment antenna height above ground, used in the propagation model.",
            ue_cable_loss_db: "Cable loss for the user equipment. In mobile devices, it is usually considered negligible.",
            ue_mimo_layers: "Number of MIMO layers representing the 2x2 configuration. In the current model, this value is stored as a scenario parameter.",
            scenario_preset: "Choose a scenario preset to quickly test common configurations without tuning all parameters manually.",
            ue_rx_sensitivity_dbm: "Minimum UE receiver sensitivity. Signals below this threshold are not accepted for connection or handover.",
            ue_rx_sensitivity_margin_db: "Tolerance margin for the receiver sensitivity check. Use positive values to accept weaker signals during handover.",
            low_bitrate_kbps: "Demanded data rate for low-bitrate users. This is the minimum throughput needed to satisfy the user service. Graph color: green.",
            low_profile_prob_pct: "Probability that a UE is randomly assigned the low-bitrate profile when created. Default value: 60%.",
            medium_bitrate_kbps: "Demanded data rate for medium-bitrate users. This is the minimum throughput needed to satisfy the user service. Graph color: yellow.",
            medium_profile_prob_pct: "Probability that a UE is randomly assigned the medium-bitrate profile when created. Default value: 30%.",
            high_bitrate_kbps: "Demanded data rate for high-bitrate users. This is the minimum throughput needed to satisfy the user service. Graph color: red.",
            high_profile_prob_pct: "Probability that a UE is randomly assigned the high-bitrate profile when created. Default value: 10%.",
            connection_attempt_mean: "Mean time between connection attempts generated by each user. The process represents random traffic arrivals in the network.",
            connection_attempt_std: "Standard deviation of the time between connection attempts. Higher values make traffic arrivals more dispersed.",
            connection_duration_mean: "Mean duration of an established connection. During this period, the user keeps PRBs allocated on the serving base station.",
            connection_duration_std: "Standard deviation of connection duration. Higher values increase variation in how long connections remain active.",
            body_loss_db: "Additional loss caused by user-body absorption or obstruction close to the terminal.",
            slow_fading_margin_db: "Margin used to represent slow channel variations, such as shadowing from buildings and obstacles.",
            foliage_loss_db: "Additional loss associated with vegetation between transmitter and receiver.",
            interference_margin_db: "Margin added to represent interference from other cells or concurrent transmissions.",
            rain_margin_db: "Rain attenuation margin. In the default scenario, rain is not considered and the value is 0 dB.",
            ric_control_period: "Period between RIC control executions. On each cycle, the MRO and MLB xApps reevaluate statistics, load, and base-station parameters.",
            mro_window: "Historical window used by MRO to calculate ping-pong and RLF ratios relative to recent handovers.",
            pingpong_period: "Maximum interval for classifying a BS #1 -> BS #2 -> BS #1 handover sequence as ping-pong. Default value: 10 seconds.",
        },
        options: {
            no_CM: "No CMF",
            prio_MRO: "MRO priority",
            prio_MLB: "MLB priority",
        },
    },
};

const scenarioPresetLabels = {
    pt: {
        default: "Padrão",
        force_handover: "Forçar handover",
        high_density: "Alta densidade",
        low_interference: "Baixa interferência",
    },
    en: {
        default: "Default",
        force_handover: "Force handover",
        high_density: "High density",
        low_interference: "Low interference",
    },
};

const scenarioPresets = {
    default: {
        sim_time: 1000,
        inter_site_distance: 600,
        n_bs: 19,
        cmf_mode: "no_CM",
        export_bs_results: true,
        bs_antenna_gain_db: 2,
        bs_height_m: 10,
        bs_cable_loss_db: 2,
        bs_tx_power_dbm: 28,
        center_freq_mhz: 2100,
        bandwidth_mhz: 20,
        subcarrier_count: 12,
        subcarrier_spacing_khz: 15,
        default_cio_db: 0,
        default_ttt_s: 0.064,
        default_hysteresis_db: 0,
        ue_rx_sensitivity_dbm: -110,
        ue_rx_sensitivity_margin_db: 0,
        n_users: 380,
        users_per_bs: 20,
        dt: 0.05,
        pedestrian_prob_pct: 80,
        pedestrian_speed: 5,
        vehicle_speed: 25,
        direction_change_prob_pct: 0.06,
        ue_antenna_gain_db: 0,
        ue_height_m: 1.6,
        ue_cable_loss_db: 0,
        ue_mimo_layers: 2,
        low_bitrate_kbps: 96,
        low_profile_prob_pct: 60,
        medium_bitrate_kbps: 5000,
        medium_profile_prob_pct: 30,
        high_bitrate_kbps: 24000,
        high_profile_prob_pct: 10,
        connection_attempt_mean: 20,
        connection_attempt_std: 3,
        connection_duration_mean: 60,
        connection_duration_std: 15,
        body_loss_db: 1,
        slow_fading_margin_db: 4,
        foliage_loss_db: 4,
        interference_margin_db: 2,
        rain_margin_db: 0,
        ric_control_period: 10,
        mro_window: 240,
        pingpong_period: 10,
    },
    force_handover: {
        sim_time: 600,
        inter_site_distance: 450,
        cmf_mode: "prio_MRO",
        default_cio_db: 1,
        default_ttt_s: 0.016,
        default_hysteresis_db: 0,
        ue_rx_sensitivity_dbm: -110,
        ue_rx_sensitivity_margin_db: 4,
        pedestrian_prob_pct: 35,
        pedestrian_speed: 3,
        vehicle_speed: 35,
        direction_change_prob_pct: 0.12,
        connection_attempt_mean: 12,
        connection_attempt_std: 2,
        pingpong_period: 12,
    },
    high_density: {
        sim_time: 800,
        inter_site_distance: 500,
        cmf_mode: "prio_MLB",
        n_users: 760,
        users_per_bs: 40,
        connection_attempt_mean: 8,
        connection_attempt_std: 2,
        connection_duration_mean: 90,
        connection_duration_std: 20,
        medium_profile_prob_pct: 45,
        high_profile_prob_pct: 20,
        low_profile_prob_pct: 35,
        interference_margin_db: 4,
        ric_control_period: 5,
    },
    low_interference: {
        sim_time: 1000,
        inter_site_distance: 800,
        cmf_mode: "no_CM",
        n_users: 285,
        users_per_bs: 15,
        bs_tx_power_dbm: 26,
        default_ttt_s: 0.128,
        default_hysteresis_db: 1,
        pedestrian_prob_pct: 90,
        vehicle_speed: 18,
        interference_margin_db: 0.5,
        foliage_loss_db: 2,
        slow_fading_margin_db: 2,
        rain_margin_db: 0,
    },
};

function $(id) {
    return document.getElementById(id);
}

function textNodeForLabel(label) {
    return Array.from(label.childNodes).find((node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim());
}

function setLabelText(inputId, text) {
    const input = $(inputId);
    const label = input ? input.closest("label") : null;
    if (!label) return;

    const span = label.querySelector("span");
    if (input.type === "checkbox" && span) {
        span.textContent = text;
        return;
    }

    const node = textNodeForLabel(label);
    if (node) {
        node.textContent = `\n                        ${text}\n                        `;
    }
}

function setLabelTooltip(inputId, text) {
    const input = $(inputId);
    const label = input ? input.closest("label") : null;
    if (label) label.title = text;
}

function setElementText(selector, text) {
    const element = document.querySelector(selector);
    if (!element) return;

    if (selector.startsWith(".legend span")) {
        const marker = element.firstElementChild;
        element.textContent = "";
        if (marker) element.appendChild(marker);
        element.append(` ${text}`);
        return;
    }

    element.textContent = text;
}

function translateStatusMessage(message) {
    const messages = {
        Idle: { pt: "Aguardando início.", en: "Idle." },
        Queued: { pt: "Na fila.", en: "Queued." },
        Starting: { pt: "Iniciando.", en: "Starting." },
        Running: { pt: "Executando.", en: "Running." },
        Finished: { pt: "Finalizada.", en: "Finished." },
        Stopping: { pt: "Parando.", en: "Stopping." },
    };

    return messages[message]?.[currentLanguage] || message || i18n[currentLanguage].statusFallback;
}

function updateStartButtonText() {
    const lang = i18n[currentLanguage];
    ["start-button", "setup-start-button"].forEach((id) => {
        const button = $(id);
        if (!button) return;

        button.textContent = simulationRunning ? lang.stopButton : lang.startButton;
        button.classList.toggle("stop-mode", simulationRunning);
        button.disabled = simulationRequestPending;
        button.setAttribute("aria-busy", simulationRequestPending.toString());
    });
}

function updateCardToggleText(card) {
    const button = card.querySelector(".parameter-card-toggle");
    if (!button) return;
    const expanded = !card.classList.contains("collapsed");
    button.textContent = card.classList.contains("collapsed")
        ? i18n[currentLanguage].expandCard
        : i18n[currentLanguage].collapseCard;
    button.setAttribute("aria-expanded", expanded.toString());
}

function enhanceSetupCards() {
    document.querySelectorAll("#setup-panel .parameter-card").forEach((card, index) => {
        if (card.querySelector(".parameter-card-toggle")) return;

        const title = card.querySelector("h3");
        if (!title) return;

        const header = document.createElement("div");
        header.className = "parameter-card-header";
        title.before(header);
        header.appendChild(title);

        const toggle = document.createElement("button");
        toggle.type = "button";
        toggle.className = "parameter-card-toggle";
        toggle.addEventListener("click", () => {
            card.classList.toggle("collapsed");
            updateCardToggleText(card);
        });
        header.appendChild(toggle);

        if (index > 1) {
            card.classList.add("collapsed");
        }

        updateCardToggleText(card);
    });
}

function applyLanguage(language) {
    currentLanguage = language;
    const lang = i18n[currentLanguage];

    document.documentElement.lang = lang.htmlLang;
    document.title = lang.documentTitle;
    $("language-toggle").textContent = lang.languageButton;

    Object.entries(lang.texts).forEach(([selector, text]) => setElementText(selector, text));
    Object.entries(lang.labels).forEach(([inputId, text]) => setLabelText(inputId, text));
    Object.entries(lang.tooltips).forEach(([inputId, text]) => setLabelTooltip(inputId, text));
    Object.entries(lang.options).forEach(([value, text]) => {
        const option = document.querySelector(`#cmf_mode option[value="${value}"]`);
        if (option) option.textContent = text;
    });
    Object.entries(scenarioPresetLabels[currentLanguage]).forEach(([value, text]) => {
        const option = document.querySelector(`#scenario_preset option[value="${value}"]`);
        if (option) option.textContent = text;
    });

    updateStartButtonText();
    updateScenarioSummary();
    document.querySelectorAll("#setup-panel .parameter-card").forEach(updateCardToggleText);
}

function toggleLanguage() {
    applyLanguage(currentLanguage === "pt" ? "en" : "pt");
}

function switchTab(name) {
    document.querySelectorAll(".tab-button").forEach((btn) => btn.classList.toggle("active", btn.id === `tab-${name}`));
    document.querySelectorAll(".tab-panel").forEach((panel) => panel.classList.toggle("active", panel.id === `${name}-panel`));
}

function formatTimestamp(ts) {
    if (!ts) return "-";
    const date = new Date(ts * 1000);
    return date.toLocaleTimeString();
}

function numberValue(id, fallback) {
    const value = parseFloat($(id).value);
    return Number.isFinite(value) ? value : fallback;
}

function setSetupFieldValue(id, value) {
    const field = $(id);
    if (!field) return;

    if (field.type === "checkbox") {
        field.checked = Boolean(value);
        return;
    }

    field.value = value;
}

function activeScenarioPresetName() {
    const preset = $("scenario_preset")?.value || "default";
    return scenarioPresetLabels[currentLanguage][preset] || preset;
}

function updateScenarioSummary() {
    const scenarioSummary = $("scenario-summary");
    const presetSummary = $("scenario-preset-summary");
    if (scenarioSummary) {
        const simTime = numberValue("sim_time", 1000);
        const users = parseInt($("n_users").value, 10) || 380;
        const antennas = parseInt($("n_bs").value, 10) || 19;
        const distance = numberValue("inter_site_distance", 600);
        scenarioSummary.textContent = `${antennas} BS, ${users} UEs, ${distance} m, ${simTime} s`;
    }
    if (presetSummary) {
        presetSummary.textContent = activeScenarioPresetName();
    }

    if (!simulationRunning && !simulationRequestPending) {
        drawConfiguredTopologyPreview();
    }
}

function applyScenarioPreset() {
    const selectedPreset = $("scenario_preset").value || "default";
    const preset = {
        ...scenarioPresets.default,
        ...(scenarioPresets[selectedPreset] || {}),
    };

    Object.entries(preset).forEach(([id, value]) => setSetupFieldValue(id, value));
    updateScenarioSummary();
}

function userProfilePayload() {
    const lowProb = numberValue("low_profile_prob_pct", 60);
    const mediumProb = numberValue("medium_profile_prob_pct", 30);
    const highProb = numberValue("high_profile_prob_pct", 10);
    const totalProb = lowProb + mediumProb + highProb || 100;

    return {
        low: {
            bitrate_bps: numberValue("low_bitrate_kbps", 96) * 1e3,
            prob: lowProb / totalProb,
            color: "green",
        },
        medium: {
            bitrate_bps: numberValue("medium_bitrate_kbps", 5000) * 1e3,
            prob: mediumProb / totalProb,
            color: "yellow",
        },
        high: {
            bitrate_bps: numberValue("high_bitrate_kbps", 24000) * 1e3,
            prob: highProb / totalProb,
            color: "red",
        },
    };
}

async function fetchState() {
    try {
        const response = await fetch(stateUrl, { cache: "no-cache" });
        if (!response.ok) {
            throw new Error(i18n[currentLanguage].fetchError);
        }
        const state = await response.json();
        updateStatus(state);
    } catch (error) {
        console.error(error);
    }
}

function updateStatus(state) {
    $("status-message").textContent = translateStatusMessage(state.message);
    $("last-update").textContent = formatTimestamp(state.last_update);
    const serverRunning = !!state.running || ["Queued", "Starting", "Running", "Stopping"].includes(state.message);
    const shouldKeepSetupPreview = setupPreviewActive && !serverRunning;

    if (state.snapshot && !shouldKeepSetupPreview) {
        $("progress").textContent = `${state.snapshot.progress || 0}%`;
        $("connected-count").textContent = state.snapshot.connected_users;
        const satisfactionValue = Number.isFinite(state.snapshot.satisfaction)
            ? state.snapshot.satisfaction
            : state.snapshot.connected_users > 0 || state.snapshot.total_blocked_attempts > 0
            ? state.snapshot.connected_users / (state.snapshot.connected_users + state.snapshot.total_blocked_attempts)
            : 0;
        $("user-satisfaction").textContent = `${(satisfactionValue * 100).toFixed(1)}%`;
        $("handovers").textContent = state.snapshot.handovers;
        $("pingpongs").textContent = state.snapshot.pingpongs;
        $("rlfs").textContent = state.snapshot.rlfs;
        $("call-blockages").textContent = state.snapshot.total_blocked_attempts;
        $("avg-load").textContent = `${(state.snapshot.avg_load * 100).toFixed(1)}%`;
        $("max-load").textContent = `${(state.snapshot.max_load * 100).toFixed(1)}%`;
        $("antenna-count").textContent = state.snapshot.bs?.length || 0;
        drawScene(state.snapshot);
    }

    const running = serverRunning;
    simulationRunning = running;
    simulationRequestPending = false;
    updateStartButtonText();
}

async function startSimulation() {
    if (simulationRequestPending) return;

    setupPreviewActive = false;
    simulationRequestPending = true;
    updateStartButtonText();

    const simTime = numberValue("sim_time", 1000);
    const dt = numberValue("dt", 0.05);
    const nUsers = parseInt($("n_users").value, 10) || 380;
    const nBs = parseInt($("n_bs").value, 10) || 19;
    const interSiteDistance = numberValue("inter_site_distance", 600);
    const cmfMode = $("cmf_mode").value || "no_CM";
    const exportBsResults = $("export_bs_results").checked;

    try {
        const response = await fetch(startUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                SIM_TIME: simTime,
                DT: dt,
                N_BS: nBs,
                N_USERS: nUsers,
                USERS_PER_BS: parseInt($("users_per_bs").value, 10) || 20,
                INTER_SITE_DISTANCE: interSiteDistance,
                BS_ANTENNA_GAIN_DB: numberValue("bs_antenna_gain_db", 2),
                BS_HEIGHT_M: numberValue("bs_height_m", 10),
                BS_CABLE_LOSS_DB: numberValue("bs_cable_loss_db", 2),
                BS_TX_POWER_DBM: numberValue("bs_tx_power_dbm", 28),
                CENTER_FREQ_GHZ: numberValue("center_freq_mhz", 2100) / 1000,
                BANDWIDTH_HZ: numberValue("bandwidth_mhz", 20) * 1e6,
                SUBCARRIER_COUNT: parseInt($("subcarrier_count").value, 10) || 12,
                SUBCARRIER_SPACING_HZ: numberValue("subcarrier_spacing_khz", 15) * 1e3,
                DEFAULT_CIO_DB: numberValue("default_cio_db", 0),
                DEFAULT_TTT_S: numberValue("default_ttt_s", 0.064),
                DEFAULT_HYSTERESIS_DB: numberValue("default_hysteresis_db", 0),
                PEDESTRIAN_PROB: numberValue("pedestrian_prob_pct", 80) / 100,
                PEDESTRIAN_SPEED: numberValue("pedestrian_speed", 5),
                VEHICLE_SPEED: numberValue("vehicle_speed", 25),
                DIRECTION_CHANGE_PROB: numberValue("direction_change_prob_pct", 0.06) / 100,
                UE_ANTENNA_GAIN_DB: numberValue("ue_antenna_gain_db", 0),
                UE_HEIGHT_M: numberValue("ue_height_m", 1.6),
                UE_CABLE_LOSS_DB: numberValue("ue_cable_loss_db", 0),
                UE_MIMO_LAYERS: parseInt($("ue_mimo_layers").value, 10) || 2,
                UE_RX_SENSITIVITY_DBM: numberValue("ue_rx_sensitivity_dbm", -110),
                UE_RX_SENSITIVITY_MARGIN_DB: numberValue("ue_rx_sensitivity_margin_db", 0),
                USER_PROFILES: userProfilePayload(),
                CONNECTION_ATTEMPT_MEAN: numberValue("connection_attempt_mean", 20),
                CONNECTION_ATTEMPT_STD: numberValue("connection_attempt_std", 3),
                CONNECTION_DURATION_MEAN: numberValue("connection_duration_mean", 60),
                CONNECTION_DURATION_STD: numberValue("connection_duration_std", 15),
                BODY_LOSS_DB: numberValue("body_loss_db", 1),
                SLOW_FADING_MARGIN_DB: numberValue("slow_fading_margin_db", 4),
                FOLIAGE_LOSS_DB: numberValue("foliage_loss_db", 4),
                INTERFERENCE_MARGIN_DB: numberValue("interference_margin_db", 2),
                RAIN_MARGIN_DB: numberValue("rain_margin_db", 0),
                RIC_CONTROL_PERIOD: numberValue("ric_control_period", 10),
                MRO_WINDOW: numberValue("mro_window", 240),
                PINGPONG_PERIOD: numberValue("pingpong_period", 10),
                export_bs_results: exportBsResults,
                cmf_mode: cmfMode,
                scenario_preset: $("scenario_preset").value || "default",
            }),
        });

        if (!response.ok) {
            const error = await response.json();
            alert(error.error || i18n[currentLanguage].startError);
            return;
        }

        const result = await response.json();
        simulationRunning = true;
        $("status-message").textContent = i18n[currentLanguage].startedMessage;
        startPolling();
    } catch (error) {
        console.error(error);
    } finally {
        simulationRequestPending = false;
        updateStartButtonText();
    }
}

async function stopSimulation() {
    if (simulationRequestPending) return;

    simulationRequestPending = true;
    updateStartButtonText();

    try {
        await fetch(stopUrl, { method: "POST" });
        simulationRunning = true;
        $("status-message").textContent = i18n[currentLanguage].stoppingMessage;
    } catch (error) {
        console.error(error);
    } finally {
        simulationRequestPending = false;
        updateStartButtonText();
    }
}

function toggleSimulation() {
    if (simulationRunning) {
        stopSimulation();
        return;
    }

    startSimulation();
}

function startPolling() {
    if (pollingTimer) return;
    pollingTimer = setInterval(fetchState, 300);
    fetchState();
}

function stopPolling() {
    if (pollingTimer) {
        clearInterval(pollingTimer);
        pollingTimer = null;
    }
}

function drawCellTower(ctx, x, y) {
    ctx.save();
    ctx.translate(x, y);
    ctx.strokeStyle = "#12324f";
    ctx.fillStyle = "#1d3557";
    ctx.lineWidth = 1.8;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";

    // Lattice tower body.
    ctx.beginPath();
    ctx.moveTo(0, -13);
    ctx.lineTo(-7, 12);
    ctx.lineTo(7, 12);
    ctx.closePath();
    ctx.stroke();

    // Cross braces.
    ctx.beginPath();
    ctx.moveTo(-4.7, 4);
    ctx.lineTo(4.7, 4);
    ctx.moveTo(-2.6, -4);
    ctx.lineTo(2.6, -4);
    ctx.moveTo(-5.5, 9);
    ctx.lineTo(2.6, -4);
    ctx.moveTo(5.5, 9);
    ctx.lineTo(-2.6, -4);
    ctx.stroke();

    // Top radio head.
    ctx.beginPath();
    ctx.arc(0, -13, 2.2, 0, Math.PI * 2);
    ctx.fill();

    // Cellular panel antennas.
    ctx.fillStyle = "#457b9d";
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.roundRect(-11, -10, 4, 12, 2);
    ctx.roundRect(7, -10, 4, 12, 2);
    ctx.fill();
    ctx.stroke();

    // Radio waves.
    ctx.strokeStyle = "#1d3557";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.arc(0, -13, 9, -0.65, 0.65);
    ctx.arc(0, -13, 9, Math.PI - 0.65, Math.PI + 0.65);
    ctx.arc(0, -13, 14, -0.55, 0.55);
    ctx.arc(0, -13, 14, Math.PI - 0.55, Math.PI + 0.55);
    ctx.stroke();

    ctx.restore();
}

function getUeProfileColor(color) {
    const profileColors = {
        green: "green",
        olive: "yellow",
        yellow: "yellow",
        darkred: "red",
        red: "red",
    };

    return profileColors[color] || color || "#94a3b8";
}

function chooseGridStep(span) {
    if (span <= 1000) return 100;
    if (span <= 2500) return 250;
    if (span <= 5000) return 500;
    if (span <= 10000) return 1000;
    return 2000;
}

function buildSceneBounds(snapshot) {
    const points = [
        ...(snapshot.area_polygon || []),
        ...(snapshot.bs || []),
        ...(snapshot.ues || []),
    ].filter(
        (point) => Number.isFinite(point.x) && Number.isFinite(point.y)
    );

    if (points.length === 0) {
        return {
            minX: -1000,
            maxX: 1000,
            minY: -1000,
            maxY: 1000,
            tickMinX: -1000,
            tickMaxX: 1000,
            tickMinY: -1000,
            tickMaxY: 1000,
            tickStep: 500,
        };
    }

    const xs = points.map((point) => point.x);
    const ys = points.map((point) => point.y);
    const rawMinX = Math.min(...xs);
    const rawMaxX = Math.max(...xs);
    const rawMinY = Math.min(...ys);
    const rawMaxY = Math.max(...ys);
    const spanX = Math.max(rawMaxX - rawMinX, 1);
    const spanY = Math.max(rawMaxY - rawMinY, 1);
    const padding = Math.max(spanX, spanY, 600) * 0.12;
    const minX = rawMinX - padding;
    const maxX = rawMaxX + padding;
    const minY = rawMinY - padding;
    const maxY = rawMaxY + padding;
    const tickStep = chooseGridStep(Math.max(maxX - minX, maxY - minY));

    return {
        minX,
        maxX,
        minY,
        maxY,
        tickMinX: Math.floor(minX / tickStep) * tickStep,
        tickMaxX: Math.ceil(maxX / tickStep) * tickStep,
        tickMinY: Math.floor(minY / tickStep) * tickStep,
        tickMaxY: Math.ceil(maxY / tickStep) * tickStep,
        tickStep,
    };
}

function alignSnapshotToAntennaOrigin(snapshot) {
    const bsPoints = (snapshot.bs || []).filter(
        (point) => Number.isFinite(point.x) && Number.isFinite(point.y)
    );

    if (bsPoints.length === 0) {
        return snapshot;
    }

    const minX = Math.min(...bsPoints.map((point) => point.x));
    const minY = Math.min(...bsPoints.map((point) => point.y));
    const shiftX = ANTENNA_DISPLAY_ORIGIN - minX;
    const shiftY = ANTENNA_DISPLAY_ORIGIN - minY;

    if (shiftX === 0 && shiftY === 0) {
        return snapshot;
    }

    const shiftPoint = (point) => ({
        ...point,
        x: point.x + shiftX,
        y: point.y + shiftY,
    });

    return {
        ...snapshot,
        bs: (snapshot.bs || []).map(shiftPoint),
        ues: (snapshot.ues || []).map(shiftPoint),
        area_polygon: (snapshot.area_polygon || []).map(shiftPoint),
        coordinateShift: { x: shiftX, y: shiftY },
    };
}

function previewBaseStations(nBs, isd) {
    const centerX = 1000;
    const centerY = 1000;
    const targetCount = Math.max(1, Number.isFinite(nBs) ? Math.trunc(nBs) : 19);
    const spacing = Number.isFinite(isd) ? isd : 600;
    const coords = [];
    let rings = 0;

    while (1 + 3 * rings * (rings + 1) < targetCount) {
        rings += 1;
    }

    for (let q = -rings; q <= rings; q += 1) {
        for (let r = -rings; r <= rings; r += 1) {
            const s = -q - r;
            if (Math.max(Math.abs(q), Math.abs(r), Math.abs(s)) <= rings) {
                coords.push({
                    x: centerX + spacing * Math.sqrt(3) * (q + r / 2),
                    y: centerY + spacing * 1.5 * r,
                });
            }
        }
    }

    return coords
        .sort((a, b) => {
            const distA = (a.x - centerX) ** 2 + (a.y - centerY) ** 2;
            const distB = (b.x - centerX) ** 2 + (b.y - centerY) ** 2;
            return distA - distB || a.y - b.y || a.x - b.x;
        })
        .slice(0, targetCount)
        .sort((a, b) => a.y - b.y || a.x - b.x)
        .map((point, index) => ({
            id: index + 1,
            x: point.x,
            y: point.y,
            load: 0,
            used_prbs: 0,
        }));
}

function convexHull(points) {
    const unique = Array.from(
        new Map(
            points
                .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y))
                .map((point) => [`${point.x},${point.y}`, { x: point.x, y: point.y }])
        ).values()
    ).sort((a, b) => a.x - b.x || a.y - b.y);

    if (unique.length <= 1) return unique;

    const cross = (origin, a, b) =>
        (a.x - origin.x) * (b.y - origin.y) - (a.y - origin.y) * (b.x - origin.x);

    const lower = [];
    unique.forEach((point) => {
        while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], point) <= 0) {
            lower.pop();
        }
        lower.push(point);
    });

    const upper = [];
    [...unique].reverse().forEach((point) => {
        while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], point) <= 0) {
            upper.pop();
        }
        upper.push(point);
    });

    return lower.slice(0, -1).concat(upper.slice(0, -1));
}

function buildSimulationPolygon(bs, isd) {
    const margin = Math.max((Number.isFinite(isd) ? isd : 600) * 1.5, 1);
    const points = bs || [];

    if (points.length === 0) return [];
    if (points.length < 3) {
        const xs = points.map((point) => point.x);
        const ys = points.map((point) => point.y);
        const minX = Math.min(...xs) - margin;
        const maxX = Math.max(...xs) + margin;
        const minY = Math.min(...ys) - margin;
        const maxY = Math.max(...ys) + margin;
        return [
            { x: minX, y: minY },
            { x: maxX, y: minY },
            { x: maxX, y: maxY },
            { x: minX, y: maxY },
        ];
    }

    const hull = convexHull(points);
    const center = {
        x: hull.reduce((sum, point) => sum + point.x, 0) / hull.length,
        y: hull.reduce((sum, point) => sum + point.y, 0) / hull.length,
    };

    return hull.map((point) => {
        const dx = point.x - center.x;
        const dy = point.y - center.y;
        const length = Math.hypot(dx, dy);
        if (length < 1e-9) return { ...point };
        return {
            x: center.x + (dx / length) * (length + margin),
            y: center.y + (dy / length) * (length + margin),
        };
    });
}

function drawConfiguredTopologyPreview() {
    const nBs = parseInt($("n_bs")?.value, 10) || 19;
    const interSiteDistance = numberValue("inter_site_distance", 600);
    const bs = previewBaseStations(nBs, interSiteDistance);
    const preview = {
        preview: true,
        step: 0,
        steps: 0,
        time: 0,
        progress: 0,
        area_polygon: buildSimulationPolygon(bs, interSiteDistance),
        bs,
        ues: [],
    };

    setupPreviewActive = true;
    $("antenna-count").textContent = preview.bs.length;
    $("progress").textContent = "0%";
    drawScene(preview);
}

function drawAxes(ctx, bounds, transformX, transformY, width, height, margin) {
    const axisOriginX = 0;
    const axisOriginY = 0;
    const axisX = transformY(axisOriginY);
    const axisY = transformX(axisOriginX);
    const tickSize = 5;

    ctx.save();
    ctx.strokeStyle = "#475569";
    ctx.fillStyle = "#334155";
    ctx.lineWidth = 1.5;
    ctx.font = "12px Inter, Arial, sans-serif";

    ctx.beginPath();
    if (axisX >= margin && axisX <= height - margin) {
        ctx.moveTo(margin, axisX);
        ctx.lineTo(width - margin, axisX);
    }
    if (axisY >= margin && axisY <= width - margin) {
        ctx.moveTo(axisY, margin);
        ctx.lineTo(axisY, height - margin);
    }
    ctx.stroke();

    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    for (let gx = bounds.tickMinX; gx <= bounds.tickMaxX; gx += bounds.tickStep) {
        const x = transformX(gx);
        const tickY = axisX >= margin && axisX <= height - margin ? axisX : height - margin;
        ctx.beginPath();
        ctx.moveTo(x, tickY - tickSize);
        ctx.lineTo(x, tickY + tickSize);
        ctx.stroke();
        ctx.fillText(gx.toString(), x, tickY + tickSize + 4);
    }

    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    for (let gy = bounds.tickMinY; gy <= bounds.tickMaxY; gy += bounds.tickStep) {
        const y = transformY(gy);
        const tickX = axisY >= margin && axisY <= width - margin ? axisY : margin;
        ctx.beginPath();
        ctx.moveTo(tickX - tickSize, y);
        ctx.lineTo(tickX + tickSize, y);
        ctx.stroke();
        ctx.fillText(gy.toString(), tickX - tickSize - 6, y);
    }

    ctx.textAlign = "right";
    ctx.textBaseline = "bottom";
    ctx.fillText("x (m)", width - margin, Math.min(Math.max(axisX - 8, margin), height - margin));

    ctx.save();
    ctx.translate(Math.min(Math.max(axisY + 16, margin + 16), width - margin), margin);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    ctx.fillText("y (m)", 0, 0);
    ctx.restore();

    ctx.restore();
}

function drawScene(snapshot) {
    const displaySnapshot = alignSnapshotToAntennaOrigin(snapshot);
    const canvas = $("simulation-canvas");
    const ctx = canvas.getContext("2d");
    const width = canvas.width;
    const height = canvas.height;
    ctx.clearRect(0, 0, width, height);

    const bounds = buildSceneBounds(displaySnapshot);
    const margin = 48;
    const scaleX = (width - margin * 2) / (bounds.maxX - bounds.minX);
    const scaleY = (height - margin * 2) / (bounds.maxY - bounds.minY);
    const scale = Math.min(scaleX, scaleY);
    const offsetX = margin - bounds.minX * scale;
    const offsetY = height - margin + bounds.minY * scale;

    const transformX = (x) => x * scale + offsetX;
    const transformY = (y) => offsetY - y * scale;

    // Background grid
    ctx.fillStyle = "#f8fafc";
    ctx.fillRect(0, 0, width, height);
    ctx.strokeStyle = "#e2e8f0";
    ctx.lineWidth = 1;
    for (let gx = bounds.tickMinX; gx <= bounds.tickMaxX; gx += bounds.tickStep) {
        const x = transformX(gx);
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
    }
    for (let gy = bounds.tickMinY; gy <= bounds.tickMaxY; gy += bounds.tickStep) {
        const y = transformY(gy);
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
    }

    drawAxes(ctx, bounds, transformX, transformY, width, height, margin);

    // Draw simulation area
    const areaPolygon = (displaySnapshot.area_polygon || []).filter(
        (point) => Number.isFinite(point.x) && Number.isFinite(point.y)
    );
    if (areaPolygon.length >= 3) {
        ctx.save();
        ctx.beginPath();
        areaPolygon.forEach((point, index) => {
            const x = transformX(point.x);
            const y = transformY(point.y);
            if (index === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        });
        ctx.closePath();
        ctx.fillStyle = "rgba(69, 123, 157, 0.08)";
        ctx.strokeStyle = "#457b9d";
        ctx.lineWidth = 2;
        ctx.fill();
        ctx.stroke();
        ctx.restore();
    }

    // Draw BS positions
    (displaySnapshot.bs || []).forEach((bs) => {
        const x = transformX(bs.x);
        const y = transformY(bs.y);
        drawCellTower(ctx, x, y);
        ctx.fillStyle = "#1d3557";
        ctx.font = "12px Inter, Arial, sans-serif";
        ctx.textAlign = "left";
        ctx.textBaseline = "middle";
        ctx.fillText(bs.id.toString(), x + 14, y - 8);
    });

    // Draw UEs
    (displaySnapshot.ues || []).forEach((ue) => {
        const x = transformX(ue.x);
        const y = transformY(ue.y);
        ctx.fillStyle = getUeProfileColor(ue.color);
        ctx.beginPath();
        ctx.arc(x, y, 3.2, 0, Math.PI * 2);
        ctx.fill();
    });

    // Draw overview text
    ctx.fillStyle = "#334155";
    ctx.font = "13px Inter, Arial, sans-serif";
    ctx.fillText(`Step ${snapshot.step}/${snapshot.steps} — ${snapshot.progress}%`, 16, 20);
    ctx.fillText(`Tempo = ${snapshot.time.toFixed(2)} s`, 16, 40);
}

function init() {
    $("tab-setup").addEventListener("click", () => switchTab("setup"));
    $("tab-visual").addEventListener("click", () => switchTab("visual"));
    $("language-toggle").addEventListener("click", toggleLanguage);
    $("setup-visual-shortcut").addEventListener("click", () => switchTab("visual"));
    $("start-button").addEventListener("click", toggleSimulation);
    $("scenario_preset").addEventListener("change", applyScenarioPreset);
    document.querySelectorAll("#setup-panel input, #setup-panel select").forEach((field) => {
        if (field.id !== "scenario_preset") {
            field.addEventListener("input", updateScenarioSummary);
            field.addEventListener("change", updateScenarioSummary);
        }
    });
    const setupStartBtn = $("setup-start-button");
    if (setupStartBtn) {
        setupStartBtn.addEventListener("click", toggleSimulation);
    }

    enhanceSetupCards();
    applyScenarioPreset();
    applyLanguage(currentLanguage);
    switchTab("setup");
    startPolling();
}

document.addEventListener("DOMContentLoaded", init);
