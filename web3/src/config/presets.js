export const presets = {
    default: { "n-bs": 19, "users-per-bs": 20, "n-users": 380, isd: 600, "pedestrian-prob": 80, "pedestrian-speed": 5, "vehicle-speed": 25, "turn-prob": 1.2, hysteresis: 0, ttt: 0.064 },
    handover: { "n-bs": 19, "users-per-bs": 22, "n-users": 420, isd: 450, "pedestrian-prob": 35, "pedestrian-speed": 4, "vehicle-speed": 36, hysteresis: 0.5, ttt: 0.05, "pingpong-period": 8 },
    density: { "n-bs": 19, "users-per-bs": 47, "n-users": 900, isd: 500, "pedestrian-prob": 75, "pedestrian-speed": 5, "vehicle-speed": 22, hysteresis: 1.5, ttt: 0.15 },
    wide: { "n-bs": 19, "users-per-bs": 16, "n-users": 300, isd: 900, "pedestrian-prob": 90, "pedestrian-speed": 4, "vehicle-speed": 18, hysteresis: 3, ttt: 0.35 },
};

export const defaultProfiles = [
    { name: "low", bitrateKbps: 96, probability: 0.60, color: [0.086, 0.639, 0.290, 1] },
    { name: "medium", bitrateKbps: 5000, probability: 0.30, color: [0.918, 0.702, 0.031, 1] },
    { name: "high", bitrateKbps: 24000, probability: 0.10, color: [0.863, 0.149, 0.149, 1] },
];
