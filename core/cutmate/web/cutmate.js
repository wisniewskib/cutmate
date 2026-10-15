/* cutmate main-timeline runtime: captions, camera punch-ins, hits, split moves (global seconds).
   Sub-composition timelines cannot move these root layers, so everything here runs on window.__timelines.main. */
(function () {
  function captions(tl, cfg) {
    const box = document.getElementById("captions");
    (cfg.pages || []).forEach((p) => {
      const page = document.createElement("div");
      page.className = "cap-page";
      box.appendChild(page);
      tl.set(page, { opacity: 1 }, p.start);
      tl.set(page, { opacity: 0 }, p.end);
      p.words.forEach(([text, t, cls]) => {
        const w = document.createElement("span");
        w.className = cls ? "cw " + cls : "cw";
        w.textContent = text;
        page.appendChild(w);
        const big = !!cls;
        tl.fromTo(w, { opacity: 0, scale: big ? 0.5 : 0.8, y: 20 },
          { opacity: 1, scale: 1, y: 0, duration: big ? 0.2 : 0.14, ease: big ? "back.out(3)" : "power3.out", immediateRender: false }, t);
      });
    });
  }

  function camera(tl, cfg) {
    tl.set("#cam", { scale: 1 }, 0);
    (cfg.cam || []).forEach(([t, s, ox, oy]) => {
      const v = { scale: s };
      if (ox != null) v.transformOrigin = (ox * 100).toFixed(1) + "% " + (oy * 100).toFixed(1) + "%";
      tl.set("#cam", v, t);
    });
  }

  function hits(tl, cfg) {
    tl.set("#flash", { opacity: 0 }, 0);
    tl.set("#shake", { x: 0, y: 0, rotation: 0 }, 0);
    (cfg.hits || []).forEach(([t, base, punch]) => {
      tl.fromTo("#flash", { opacity: 0.8 }, { opacity: 0, duration: 0.22, ease: "power2.out", immediateRender: false }, t);
      const amp = 24, steps = Math.round(0.35 / 0.033), pts = [];
      for (let i = 1; i <= steps; i++) {
        const k = amp * (1 - i / steps);
        pts.push({ x: Math.sin(i * 2.7) * k, y: Math.cos(i * 3.9) * k * 0.8, rotation: Math.sin(i * 1.9) * k * 0.04, duration: 0.033, ease: "none" });
      }
      pts[pts.length - 1] = { x: 0, y: 0, rotation: 0, duration: 0.033, ease: "none" };
      tl.to("#shake", { keyframes: pts }, t);
      if (punch > 0) {
        tl.fromTo("#cam", { scale: base }, { scale: base * 1.18, duration: 0.12, ease: "expo.out", immediateRender: false }, t);
        tl.fromTo("#cam", { scale: base * 1.18 }, { scale: base, duration: punch, ease: "power2.inOut", immediateRender: false }, t + 0.12);
      }
    });
  }

  function splits(tl, cfg) {
    tl.set("#split", { y: 0 }, 0);
    tl.set("#captions", { y: 0 }, 0);
    (cfg.splits || []).forEach(([tIn, tOut]) => {
      tl.fromTo("#split", { y: 0 }, { y: 300, duration: 0.45, ease: "power3.out", immediateRender: false }, tIn);
      tl.fromTo("#captions", { y: 0 }, { y: -300, duration: 0.45, ease: "power3.out", immediateRender: false }, tIn);
      tl.fromTo("#split", { y: 300 }, { y: 0, duration: 0.4, ease: "power3.inOut", immediateRender: false }, tOut);
      tl.fromTo("#captions", { y: -300 }, { y: 0, duration: 0.4, ease: "power3.inOut", immediateRender: false }, tOut);
    });
  }

  window.Cutmate = {
    build(tl, cfg) { captions(tl, cfg); camera(tl, cfg); hits(tl, cfg); splits(tl, cfg); },
  };
})();
