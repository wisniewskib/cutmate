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
    // a bg effect that draws the speaker cut-out itself: its hosts (.cm-shake) shake with the A-roll, so the cut-out
    // never ghosts against it
    const shake = cfg.shake_hosts ? "#shake, .cm-shake" : "#shake";
    tl.set(shake, { x: 0, y: 0, rotation: 0 }, 0);
    (cfg.hits || []).forEach(([t, base, punch, flash]) => {   // flash: a softer peak (a bg effect's own reveal)
      tl.fromTo("#flash", { opacity: flash == null ? 0.8 : flash }, { opacity: 0, duration: 0.22, ease: "power2.out", immediateRender: false }, t);
      const amp = 24, steps = Math.round(0.35 / 0.033), pts = [];
      for (let i = 1; i <= steps; i++) {
        const k = amp * (1 - i / steps);
        pts.push({ x: Math.sin(i * 2.7) * k, y: Math.cos(i * 3.9) * k * 0.8, rotation: Math.sin(i * 1.9) * k * 0.04, duration: 0.033, ease: "none" });
      }
      pts[pts.length - 1] = { x: 0, y: 0, rotation: 0, duration: 0.033, ease: "none" };
      tl.to(shake, { keyframes: pts }, t);
      if (punch > 0) {
        tl.fromTo("#cam", { scale: base }, { scale: base * 1.18, duration: 0.12, ease: "expo.out", immediateRender: false }, t);
        tl.fromTo("#cam", { scale: base * 1.18 }, { scale: base, duration: punch, ease: "power2.inOut", immediateRender: false }, t + 0.12);
      }
    });
  }

  function splits(tl, cfg) {
    tl.set("#split", { y: 0 }, 0);
    tl.set("#captions", { y: 0 }, 0);
    (cfg.splits || []).forEach(([tIn, tOut, dy, capDy, open]) => {
      if (dy == null) {   // a split: [tIn, tOut]
        tl.fromTo("#split", { y: 0 }, { y: 300, duration: 0.45, ease: "power3.out", immediateRender: false }, tIn);
        tl.fromTo("#captions", { y: 0 }, { y: -300, duration: 0.45, ease: "power3.out", immediateRender: false }, tIn);
        tl.fromTo("#split", { y: 300 }, { y: 0, duration: 0.4, ease: "power3.inOut", immediateRender: false }, tOut);
        tl.fromTo("#captions", { y: -300 }, { y: 0, duration: 0.4, ease: "power3.inOut", immediateRender: false }, tOut);
        return;
      }
      // the persistent panel: [tIn, tOut | null (stays), dy, capDy, open (1 = already up at 0 s, no move in)]
      const layers = [["#split", dy], ["#captions", capDy]].filter(([, v]) => v);
      layers.forEach(([sel, v]) => {
        // (a zero-length tl.set at 0 after the reset above does not hold in the renderer: hold v with a fromTo)
        if (open) tl.fromTo(sel, { y: v }, { y: v, duration: 0.01, ease: "none", immediateRender: true }, 0);
        else tl.fromTo(sel, { y: 0 }, { y: v, duration: 0.45, ease: "power3.out", immediateRender: false }, tIn);
        if (tOut != null) tl.fromTo(sel, { y: v }, { y: 0, duration: 0.4, ease: "power3.inOut", immediateRender: false }, tOut);
      });
    });
  }

  function sides(tl, cfg) {
    if (!(cfg.sides || []).length) return;
    tl.set("#split", { x: 0 }, 0);
    cfg.sides.forEach(([tIn, tOut, dx]) => {
      tl.fromTo("#split", { x: 0 }, { x: dx, duration: 0.45, ease: "power3.out", immediateRender: false }, tIn);
      tl.fromTo("#split", { x: dx }, { x: 0, duration: 0.4, ease: "power3.inOut", immediateRender: false }, tOut);
    });
  }

  function hides(tl, cfg) {   // hosts covered by an opaque layer: [selector, a, fade-out, b | null, fade-in]
    (cfg.hide || []).forEach(([sel, a, da, b, db]) => {
      tl.fromTo(sel, { opacity: 1 }, { opacity: 0, duration: da, ease: "none", immediateRender: false }, a);
      if (b != null) tl.fromTo(sel, { opacity: 0 }, { opacity: 1, duration: db, ease: "none", immediateRender: false }, b - db);
    });
  }

  window.Cutmate = {
    build(tl, cfg) { captions(tl, cfg); camera(tl, cfg); hits(tl, cfg); splits(tl, cfg); sides(tl, cfg); hides(tl, cfg); },
  };
})();
