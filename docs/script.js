const scroll = new LocomotiveScroll({
  el: document.querySelector("[data-scroll-container]"),
  smooth: true,
  lerp: 0.07,
  smartphone: { smooth: true },
  tablet: { smooth: true }
});

for (const btn of document.querySelectorAll(".copy")) {
  btn.addEventListener("click", async () => {
    const code = btn.dataset.copy;
    const state = btn.querySelector(".copy-state");
    try {
      await navigator.clipboard.writeText(code);
      if (state) {
        state.textContent = "copied";
        btn.classList.add("copied");
        setTimeout(() => {
          state.textContent = "copy";
          btn.classList.remove("copied");
        }, 1500);
      }
    } catch {
      if (state) state.textContent = "failed";
    }
  });
}

document.querySelectorAll('a[href^="#"]').forEach((a) => {
  a.addEventListener("click", (e) => {
    const id = a.getAttribute("href");
    if (id.length > 1) {
      const t = document.querySelector(id);
      if (t) {
        e.preventDefault();
        scroll.scrollTo(t);
      }
    }
  });
});
