(() => {
  const button = document.getElementById("user-button");
  const panel = document.getElementById("user-panel");
  if (!button || !panel) {
    return;
  }

  const close = () => {
    panel.hidden = true;
    button.setAttribute("aria-expanded", "false");
  };

  button.addEventListener("click", (event) => {
    event.stopPropagation();
    const opening = panel.hidden;
    panel.hidden = !opening;
    button.setAttribute("aria-expanded", String(opening));
  });

  document.addEventListener("click", (event) => {
    if (!panel.hidden && !panel.contains(event.target)) {
      close();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      close();
    }
  });
})();
