export function emptyMetrics() {
    return {
        connected: 0,
        satisfaction: 0,
        handovers: 0,
        pingpong: 0,
        rlf: 0,
        blocked: 0,
        avgLoad: 0,
    };
}

export function updateAggregateMetrics(state) {
    const connectedUsers = state.users.filter((user) => user.connected);
    state.metrics.connected = connectedUsers.length;
    state.metrics.satisfaction = connectedUsers.length
        ? connectedUsers.reduce((sum, user) => sum + user.satisfaction, 0) / connectedUsers.length
        : 0;
    state.metrics.avgLoad = state.bs.length
        ? state.bs.reduce((sum, bs) => sum + bs.load, 0) / state.bs.length
        : 0;
}
