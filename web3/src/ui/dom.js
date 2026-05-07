export const $ = (id) => document.getElementById(id);

export function switchTab(name, onAfterSwitch = () => {}) {
    document.querySelectorAll(".tab-button").forEach((button) => {
        const selected = button.id === `tab-${name}`;
        button.classList.toggle("active", selected);
        button.setAttribute("aria-selected", selected ? "true" : "false");
    });
    document.querySelectorAll(".tab-panel").forEach((panel) => {
        panel.classList.toggle("active", panel.id === `${name}-panel`);
    });
    onAfterSwitch();
}
