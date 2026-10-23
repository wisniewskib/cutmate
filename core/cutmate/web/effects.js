/* cutmate effect helpers (U.*) for sub-compositions. Deterministic: everything is a function of the composition's
   LOCAL time t, driven by one paused GSAP timeline. U.clock owns the only onUpdate. */
(function () {
  function seed(n) {                      // mulberry32
    let a = (n >>> 0) || 1;
    return function () {
      a = (a + 0x6d2b79f5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  // [x, y] at local time t, or null where nothing was tracked: > 0.25 s before the first / after the last sample,
  // or between two samples > 0.5 s apart (the hand was out of view)
  function trackAt(track, t) {
    if (!track || !track.length) return null;
    const first = track[0], last = track[track.length - 1];
    if (t <= first[0]) return first[0] - t > 0.25 ? null : [first[1], first[2]];
    if (t >= last[0]) return t - last[0] > 0.25 ? null : [last[1], last[2]];
    for (let i = 1; i < track.length; i++) {
      const b = track[i];
      if (t <= b[0]) {
        const a = track[i - 1];
        if (b[0] - a[0] > 0.5) return null;
        const f = (t - a[0]) / (b[0] - a[0] || 1);
        return [a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f];
      }
    }
    return [last[1], last[2]];
  }

  // particle i at time t: born every life/count, moves out from the emitter position at its birth, spins, fades
  function particleState(i, t, o) {
    const r = seed((o.seed || 1) * 7919 + i * 104729);
    const ang = r() * Math.PI * 2, sp = (o.speed || 100) * (0.4 + r() * 0.6), size = (o.size || 4) * (0.5 + r());
    const life = o.life || 1, born = (i / o.count) * life;
    const age = ((t - born) % life + life) % life;
    const e = o.emitter(t - age);
    if (!e) return { x: 0, y: 0, alpha: 0, size, color: (o.colors || ["#ffffff"])[0] };
    const [ex, ey] = e;
    const a2 = ang + (o.spin || 0) * age;
    return { x: ex + Math.cos(a2) * sp * age, y: ey + Math.sin(a2) * sp * age, alpha: 1 - age / life, size,
             color: (o.colors || ["#ffffff"])[Math.floor(r() * (o.colors || [1]).length)] };
  }

  const SCRAMBLE = "!<>-_\\/[]{}=+*^?#ABCDEFGHJKLMNPQRSTUVWXYZ0123456789";

  // text decoding at progress p (0–1) on frame `frame`: the first round(p·len) characters are final, the others are
  // drawn from `chars` by a seeded generator per (character, frame) — a pure function (GSAP's ScrambleTextPlugin uses
  // Math.random, so two renders would differ). Whitespace stays whitespace. Characters, not UTF-16 units
  function scrambleAt(text, p, frame, seed0, chars) {
    const cs = Array.from(chars || SCRAMBLE), tx = Array.from(String(text));
    const n = Math.round(Math.min(1, Math.max(0, Number(p) || 0)) * tx.length);
    return tx.map((c, i) => (i < n || /\s/.test(c) ? c
      : cs[Math.floor(seed((seed0 || 1) * 7919 + i * 104729 + (frame | 0))() * cs.length)])).join("");
  }

  // how open (0–1) at t from samples [[t, open], …]: a linear ramp toward the latest sample's state — up over `rise` s,
  // down over `fall` s — replayed from the start using only the samples <= t (so any frame is computed alone)
  function openAmount(series, t, rise, fall) {
    rise = rise ?? 0.3; fall = fall ?? 0.25;
    let v = 0, at = null, goal = 0;
    const step = (to) => {
      if (at === null) return;
      const dt = to - at;
      v = goal > v ? Math.min(goal, v + dt / Math.max(1e-6, rise)) : Math.max(goal, v - dt / Math.max(1e-6, fall));
    };
    for (const s of series || []) {
      if (!(s[0] <= t)) break;
      step(s[0]);
      at = s[0]; goal = Math.min(1, Math.max(0, Number(s[1]) || 0));
    }
    step(t);
    return Math.min(1, Math.max(0, v));
  }

  // the largest free rect of a region {w, h, caption_band: [y0, y1]?} above or below the burned captions (region px,
  // a small pad off the band); the whole region when there is no band. Effects fit their content into it
  function safeBox(p) {
    const w = p.w, h = p.h, b = p.caption_band;
    if (!Array.isArray(b) || b.length < 2 || !(b[1] > b[0])) return { x: 0, y: 0, w, h };
    const pad = 0.012 * h;
    const above = Math.max(0, Math.min(h, b[0] - pad)), below = Math.max(0, h - Math.max(0, b[1] + pad));
    return above >= below ? { x: 0, y: 0, w, h: above } : { x: 0, y: h - below, w, h: below };
  }

  const ANIME_ERR = "cutmate U.anime: pass an anime.js timeline (autoplay: false) or a promise resolving to { timeline: tl }";
  // anime.js timers are thenable: then() waits for the end, which a paused (seeked) timeline never reaches, so a promise
  // resolving to a bare timeline would hang the build silently. Once an effect hands U.anime a promise, awaiting any
  // anime timer fails with a one-line error instead (nothing in a seeked render may wait for playback to finish)
  function animeGuard() {
    const A = typeof window !== "undefined" && window.anime;
    if (!A || typeof A.createTimeline !== "function") return;
    let o = Object.getPrototypeOf(A.createTimeline({ autoplay: false }));
    while (o && !Object.prototype.hasOwnProperty.call(o, "then")) o = Object.getPrototypeOf(o);
    if (!o || o.then.__cutmate) return;
    const then = function () {
      throw new Error("cutmate U.anime: an anime timeline was awaited — resolve the promise to { timeline: tl }, not tl");
    };
    then.__cutmate = true;
    Object.defineProperty(o, "then", { value: then, configurable: true, writable: true });
  }

  function make(tl, root, cid, P) {
    const D = Math.max(0.001, P.dur || 1);
    const U = {};
    U.seed = seed;
    U.trackAt = trackAt;
    U.safeBox = function (p) { return safeBox(p || P); };
    // the first frame waits for p (fonts, models, measuring): registers / extends window.__hf.buildReady[cid]
    U.ready = function (p) {
      const hf = (window.__hf = window.__hf || {});
      hf.buildReady = hf.buildReady || {};
      const prev = hf.buildReady[cid];
      hf.buildReady[cid] = prev ? Promise.all([prev, p]) : Promise.resolve(p);
      return p;
    };
    // true when the theme's --panel-bg is light (Rec.709 luma > 150): explainers then draw text on the panel in --ink,
    // soften shadows and drop the glow; a dark (or unreadable) panel colour is false
    U.panelLight = function (el) {
      if (typeof document === "undefined" || typeof getComputedStyle === "undefined") return false;
      const pr = document.createElement("i");
      pr.style.color = "var(--panel-bg, #0b0b0f)";
      (el || root).appendChild(pr);
      const m = String(getComputedStyle(pr).color || "").match(/[\d.]+/g);
      pr.remove();
      return !!(m && m.length >= 3 && 0.2126 * m[0] + 0.7152 * m[1] + 0.0722 * m[2] > 150);
    };
    // resolves once the theme font is loaded in these weights (text is measured after this)
    U.fonts = function (weights, family) {
      if (typeof document === "undefined" || !document.fonts) return Promise.resolve();
      const fam = family || getComputedStyle(document.documentElement).getPropertyValue("--font").trim() || "Inter";
      return Promise.all((weights || [500, 800, 900]).map((wt) => document.fonts.load(wt + " 10px " + fam)))
        .catch(() => null);
    };
    // when a panel item's (P.panel) explainer build-in is done (card, structure and most content readable): min(0.5 s,
    // 35 % of the span) — inside the min(0.6 s, 40 %) budget with a frame or two to spare; later beats (count-up,
    // toggles, strike, tokens) may run after it. Classic split / side explainers keep their natural pace
    U.fullAt = function (at, end) { return at + Math.min(0.5, 0.35 * Math.max(0, end - at)); };
    // the numbers' font family: the theme's optional digit font (--font-num), else its display font
    U.numFamily = function () {
      if (typeof document === "undefined" || typeof getComputedStyle === "undefined") return "";
      const cs = getComputedStyle(document.documentElement);
      return String(cs.getPropertyValue("--font-num") || "").trim() || String(cs.getPropertyValue("--font-display") || "").trim();
    };
    // every U.clock callback runs from ONE tween, always in registration order: GSAP renders a timeline's children
    // last-to-first when it seeks backwards, so separate tweens would let a reader (DOM writes) run before the writer
    // (an anime seek) and show the previous frame's state — a render worker scrubbing back would differ
    let clocks = null;
    U.clock = function (fn) {
      if (!clocks) {
        clocks = [];
        const c = { t: 0 };
        tl.to(c, { t: D, duration: D, ease: "none", onUpdate: () => { for (const f of clocks) f(c.t); } }, 0);
      }
      clocks.push(fn);
      fn(0);
    };
    // the theme token `--name` as computed on the effect's root (so a theme / panel override applies), trimmed; the
    // fallback when it is empty or there is no DOM. Canvas / WebGL colours and fonts come from here
    U.token = function (name, fallback) {
      const k = String(name).startsWith("--") ? String(name) : "--" + name;
      try {
        if (typeof getComputedStyle !== "function") return fallback;
        const v = String(getComputedStyle(root).getPropertyValue(k) || "").trim();
        return v || fallback;
      } catch (e) { return fallback; }
    };
    // decodes `text` into el from `from` over `dur` s (scrambleAt with frame = floor(t·30)); final from from + dur on
    U.scramble = function (el, text, o) {
      o = o || {};
      const from = o.from ?? P.at ?? 0, dur = o.dur ?? 0.6, sd = o.seed ?? 1, chars = o.chars || SCRAMBLE;
      U.clock((t) => {
        const p = dur > 0 ? Math.min(1, Math.max(0, (t - from) / dur)) : (t >= from ? 1 : 0);
        const s = scrambleAt(text, p, Math.floor(t * 30 + 1e-6), sd, chars);
        if (el.textContent !== s) el.textContent = s;
      });
    };
    U.follow = function (el, track) {
      if (!track || !track.length) { tl.set(el, { autoAlpha: 0 }, 0); return; }
      tl.set(el, { position: "absolute", left: 0, top: 0, xPercent: -50, yPercent: -50, x: track[0][1], y: track[0][2] }, 0);
      for (let i = 1; i < track.length; i++) {
        const a = track[i - 1], b = track[i];
        tl.to(el, { x: b[1], y: b[2], duration: Math.max(0.001, b[0] - a[0]), ease: "none", immediateRender: false }, a[0]);
      }
    };
    U.particles = function (target, o) {
      const n = o.count || 100;
      if (target.getContext) {                       // Canvas 2D
        const g = target.getContext("2d");
        return { update(t) {
          g.clearRect(0, 0, target.width, target.height);
          g.globalCompositeOperation = "lighter";
          for (let i = 0; i < n; i++) {
            const p = particleState(i, t, Object.assign({ count: n }, o));
            g.globalAlpha = Math.max(0, p.alpha);
            g.fillStyle = p.color;
            g.beginPath(); g.arc(p.x, p.y, p.size, 0, Math.PI * 2); g.fill();
          }
        } };
      }
      const { THREE, scene } = target;               // THREE.Points inside U.three
      const pos = new Float32Array(n * 3), geo = new THREE.BufferGeometry();
      geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
      const mat = new THREE.PointsMaterial({ size: o.size || 0.03, color: (o.colors || ["#ffffff"])[0], transparent: true,
                                             blending: THREE.AdditiveBlending, depthWrite: false });
      const pts = new THREE.Points(geo, mat);
      scene.add(pts);
      return { points: pts, update(t) {
        for (let i = 0; i < n; i++) {
          const p = particleState(i, t, Object.assign({ count: n }, o));
          pos[i * 3] = p.x; pos[i * 3 + 1] = p.y; pos[i * 3 + 2] = 0;
        }
        geo.attributes.position.needsUpdate = true;
      } };
    };
    U.three = function (opt) {
      opt = opt || {};
      const w = opt.w || P.w, h = opt.h || P.h;
      const ready = (async () => {
        const THREE = await import("three");
        const canvas = document.createElement("canvas");
        canvas.width = w; canvas.height = h;
        Object.assign(canvas.style, { position: "absolute", left: 0, top: 0, width: w + "px", height: h + "px" });
        (opt.el || root).appendChild(canvas);
        const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, preserveDrawingBuffer: true });
        renderer.setPixelRatio(1); renderer.setSize(w, h, false); renderer.setClearColor(0x000000, 0);
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera((opt.camera && opt.camera.fov) || 35, w / h, 0.1, 100);
        camera.position.set(0, 0, (opt.camera && opt.camera.z) || 10);
        let composer = null;
        if (opt.bloom) {
          const { EffectComposer } = await import("three/addons/postprocessing/EffectComposer.js");
          const { RenderPass } = await import("three/addons/postprocessing/RenderPass.js");
          const { UnrealBloomPass } = await import("three/addons/postprocessing/UnrealBloomPass.js");
          const { OutputPass } = await import("three/addons/postprocessing/OutputPass.js");
          const { ShaderPass } = await import("three/addons/postprocessing/ShaderPass.js");
          const VS = "varying vec2 vUv; void main(){ vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0); }";
          // the bloom composite writes alpha 1 everywhere, which alone would paint the whole frame black. Two fixes:
          // alpha "luma" (default): rebuild alpha from brightness (premultiplied), so the glow composites like light
          //   (≈ screen) over the A-roll.
          // alpha "keep": save the clean render before the bloom and merge after it: object pixels keep their own
          //   alpha (solid, dark parts stay opaque), the added glow gets alpha from its brightness.
          const keep = opt.bloom.alpha === "keep";
          composer = new EffectComposer(renderer);
          composer.addPass(new RenderPass(scene, camera));
          let save = null;
          if (keep) {
            const { SavePass } = await import("three/addons/postprocessing/SavePass.js");
            save = new SavePass();
            composer.addPass(save);
          }
          composer.addPass(new UnrealBloomPass(new THREE.Vector2(w, h), opt.bloom.strength ?? 1.5, opt.bloom.radius ?? 0.5, opt.bloom.threshold ?? 0));
          if (keep) {
            const merge = new ShaderPass({ uniforms: { tDiffuse: { value: null }, tBase: { value: null } }, vertexShader: VS,
              fragmentShader: "uniform sampler2D tDiffuse; uniform sampler2D tBase; varying vec2 vUv; void main(){ vec4 b=texture2D(tBase,vUv);"
                + " vec3 g=max(texture2D(tDiffuse,vUv).rgb-b.rgb,0.0); float ga=clamp(max(g.r,max(g.g,g.b)),0.0,1.0); gl_FragColor=vec4(b.rgb+g, max(b.a,ga)); }",
            });
            merge.uniforms.tBase.value = save.renderTarget.texture;   // after construction: ShaderPass clones its uniforms
            composer.addPass(merge);
          }
          composer.addPass(new OutputPass());
          if (!keep) {
            composer.addPass(new ShaderPass({ uniforms: { tDiffuse: { value: null } }, vertexShader: VS,
              fragmentShader: "uniform sampler2D tDiffuse; varying vec2 vUv; void main(){ vec3 c=clamp(texture2D(tDiffuse,vUv).rgb,0.0,1.0);"
                + " gl_FragColor=vec4(c, max(c.r, max(c.g, c.b))); }",
            }));
          }
        }
        const toWorld = function (xPx, yPx, z) {    // frame pixels → point on the plane z (default 0)
          camera.updateMatrixWorld(); camera.updateProjectionMatrix();   // valid before the first render too
          const v = new THREE.Vector3((xPx / w) * 2 - 1, -(yPx / h) * 2 + 1, 0.5).unproject(camera);
          const dir = v.sub(camera.position).normalize();
          const d = ((z || 0) - camera.position.z) / dir.z;
          return camera.position.clone().add(dir.multiplyScalar(d));
        };
        const render = () => (composer ? composer.render() : renderer.render(scene, camera));
        return { THREE, scene, camera, renderer, composer, toWorld, render, w, h };
      })();
      return U.ready(ready);
    };
    // world point (THREE.Vector3 or [x, y, z]) → [x, y] in region px (DOM labels over a WebGL object)
    U.toScreen = function (three, v3) {
      const { THREE, camera } = three;
      const w = three.w || P.w, h = three.h || P.h;
      camera.updateMatrixWorld(); camera.updateProjectionMatrix();
      const v = (v3 && v3.isVector3 ? v3.clone() : new THREE.Vector3(v3[0], v3[1], v3[2])).project(camera);
      return [(v.x + 1) / 2 * w, (1 - v.y) / 2 * h];
    };
    // pmndrs postprocessing on a U.three() scene (instead of three's own bloom): Bloom, GodRays (≤ 60 samples, half
    // resolution), ChromaticAberration, Vignette merged into one EffectPass. alpha "luma": a last pass rebuilds alpha
    // from brightness (the glow composites like light over the A-roll, as U.three does); "opaque": a full-frame scene.
    // render() passes delta 0, so effect time never comes from the composer's wall clock. GlitchEffect is forbidden
    U.post = function (three, o) {
      o = o || {};
      return U.ready((async () => {
        const PP = await import("postprocessing");
        const { THREE, renderer, scene, camera } = three;
        if (o.alpha === "opaque") renderer.setClearColor(0x000000, 1);
        const composer = new PP.EffectComposer(renderer, { frameBufferType: THREE.HalfFloatType });
        composer.addPass(new PP.RenderPass(scene, camera));
        const fx = {}, list = [];
        if (o.bloom) {
          fx.bloom = new PP.BloomEffect({ intensity: o.bloom.intensity ?? 1, luminanceThreshold: o.bloom.threshold ?? 0.6,
                                          radius: o.bloom.radius ?? 0.6, mipmapBlur: true, resolutionScale: 0.5 });
          list.push(fx.bloom);
        }
        if (o.godrays && o.godrays.source) {
          const g = o.godrays;
          fx.godrays = new PP.GodRaysEffect(camera, g.source, { density: g.density ?? 0.96, decay: g.decay ?? 0.92,
            weight: g.weight ?? 0.4, samples: Math.min(60, g.samples ?? 60), resolutionScale: 0.5, blur: true });
          list.push(fx.godrays);
        }
        if (o.chroma) {
          const off = o.chroma.offset ?? 0.002;
          fx.chroma = new PP.ChromaticAberrationEffect({ offset: Array.isArray(off) ? new THREE.Vector2(off[0], off[1])
            : off && off.isVector2 ? off : new THREE.Vector2(off, off * 0.5), radialModulation: false });
          list.push(fx.chroma);
        }
        if (o.vignette) list.push(new PP.VignetteEffect({ offset: 0.35, darkness: 0.55 }));
        if (list.length) composer.addPass(new PP.EffectPass(camera, ...list));
        if (o.alpha !== "opaque") {
          composer.addPass(new PP.EffectPass(camera, new PP.Effect("CmLumaAlpha",
            "void mainImage(const in vec4 i, const in vec2 uv, out vec4 o){ vec3 c=clamp(i.rgb,0.,1.); o=vec4(c, max(i.a, max(c.r,max(c.g,c.b)))); }")));
        }
        composer.setSize(three.w || P.w, three.h || P.h, false);
        return { composer, effects: fx, render: () => composer.render(0) };
      })());
    };
    U.glowOrb = function (three, o) {
      o = o || {};
      const { THREE, scene } = three;
      const c1 = new THREE.Color((o.colors && o.colors[0]) || "#e0f7ff"), c2 = new THREE.Color((o.colors && o.colors[1]) || "#38bdf8");
      const mat = new THREE.ShaderMaterial({
        transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
        uniforms: { uTime: { value: 0 }, uIn: { value: c1 }, uOut: { value: c2 }, uNoise: { value: o.noise ?? 1.0 }, uShell: { value: 0 } },
        vertexShader: "varying vec3 vN; varying vec3 vP; void main(){ vN=normalize(normalMatrix*normal); vP=position; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0); }",
        fragmentShader: [
          "uniform float uTime; uniform vec3 uIn; uniform vec3 uOut; uniform float uNoise; uniform float uShell; varying vec3 vN; varying vec3 vP;",
          "float h(vec3 p){ return fract(sin(dot(p, vec3(12.9898,78.233,37.719)))*43758.5453); }",
          "float n(vec3 p){ vec3 i=floor(p), f=fract(p); f=f*f*(3.0-2.0*f);",
          " return mix(mix(mix(h(i),h(i+vec3(1,0,0)),f.x),mix(h(i+vec3(0,1,0)),h(i+vec3(1,1,0)),f.x),f.y),",
          "            mix(mix(h(i+vec3(0,0,1)),h(i+vec3(1,0,1)),f.x),mix(h(i+vec3(0,1,1)),h(i+vec3(1,1,1)),f.x),f.y),f.z); }",
          "float fbm(vec3 p){ float s=0.0, a=0.5; for(int k=0;k<4;k++){ s+=a*n(p); p*=2.0; a*=0.5; } return s; }",
          // core (uShell 0): bright centre fading to a coloured rim; shells (uShell 1): mostly clear, swirling streaks
          "void main(){ float fr=pow(1.0-abs(dot(vN, vec3(0,0,1))), 2.0);",
          " float sw=fbm(normalize(vP)*3.5 + vec3(uTime*1.7, -uTime*2.3, uTime));",
          " float st=smoothstep(0.45, 0.65, sw) * uNoise;",
          " vec3 core=mix(uIn, uOut, fr); float ca=mix(0.6, 0.25, fr) * (0.7 + 0.6*sw);",
          " vec3 shell=uOut; float sa=st*0.8 + fr*0.2;",
          " gl_FragColor=vec4(mix(core, shell, uShell), clamp(mix(ca, sa, uShell), 0.0, 1.0)); }"].join("\n"),
      });
      const r = o.radius || 0.5;
      const group = new THREE.Group();
      const core = new THREE.Mesh(new THREE.SphereGeometry(r, 48, 48), mat);
      const shells = [1.15, 1.35].map((k) => {
        const s = new THREE.Mesh(new THREE.SphereGeometry(r * k, 32, 32), mat.clone());
        s.material.uniforms.uNoise.value = o.noise ?? 1.0;
        s.material.uniforms.uShell.value = 1;
        group.add(s); return s;
      });
      group.add(core); scene.add(group);
      return { group, update(t) {
        core.material.uniforms.uTime.value = t;
        shells.forEach((s, i) => { s.material.uniforms.uTime.value = t * (1.3 + i); s.rotation.y = t * (i ? -3 : 4) * (o.swirl ?? 1); s.rotation.x = t * 1.7; });
      } };
    };
    U.draw = function (sel, o) {
      o = o || {};
      tl.fromTo(sel, { drawSVG: "0%" }, { drawSVG: "100%", duration: o.dur || 0.8, stagger: o.stagger || 0, ease: "power2.inOut" }, o.from ?? P.at ?? 0);
    };
    U.rough = function (svg, shapes, o) {
      const rc = window.rough.svg(svg);
      return shapes.map((s) => { const node = rc[s.kind](...s.args, Object.assign({ seed: (o && o.seed) || 1 }, s.opts || {})); svg.appendChild(node); return node; });
    };
    U.tex = function (el, latex) {
      window.katex.render(latex, el, { throwOnError: false });
      return el.querySelectorAll(".mord, .mbin, .mrel, .mopen, .mclose, .mpunct");
    };
    // seeks an anime.js timeline (autoplay: false; never on window.__hfAnime) from the clock. A promise (async setup:
    // fonts, measuring) goes to U.ready and must resolve to { timeline } — an anime timeline is itself thenable and
    // awaiting a paused one never ends — or to a non-thenable object with seek(ms). Until then the clock does nothing.
    // Resolving to anything else rejects the build with a one-line error (a bare timeline included: see animeGuard)
    U.anime = function (x) {
      let anim = null, last = 0;
      const pick = (v) => (v && typeof v.seek === "function" ? v : v && v.timeline && typeof v.timeline.seek === "function" ? v.timeline : null);
      anim = pick(x);
      U.clock((t) => { last = t; if (anim) anim.seek(t * 1000); });
      if (!anim && x && typeof x.then === "function") {
        animeGuard();
        U.ready(Promise.resolve(x).then((v) => {
          anim = pick(v);
          if (!anim) throw new Error(ANIME_ERR + " (got " + (v === null ? "null" : typeof v) + ")");
          anim.seek(last * 1000);
        }));
      } else if (!anim) {
        throw new Error(ANIME_ERR);
      }
      return x;
    };
    U.lottie = function (anim) { U.clock((t) => anim.goToAndStop(t * 1000, false)); return anim; };
    return U;
  }

  // ---- kinetic-word's pure helpers (CutmateFX.wow) ----
  // n points of a grid centred in W x H: cols = ceil(sqrt(n·W/H)) columns, rows filled left to right, top to bottom
  function gridSize(n, W, H) {
    const cols = Math.max(1, Math.ceil(Math.sqrt((n * W) / H))), rows = Math.max(1, Math.ceil(n / cols));
    return { cols, rows, sp: Math.min(W / cols, H / rows) };
  }
  function gridStart(n, W, H) {
    const { cols, sp } = gridSize(n, W, H), rows = Math.max(1, Math.ceil(n / cols));
    const x0 = (W - (cols - 1) * sp) / 2, y0 = (H - (rows - 1) * sp) / 2;
    return Array.from({ length: n }, (_, i) => [x0 + (i % cols) * sp, y0 + Math.floor(i / cols) * sp]);
  }
  // n targets from the glyph points: a seeded Fisher–Yates shuffle (same seed, same targets); repeats wrap when n > points
  function assignTargets(points, n, sd) {
    if (!points || !points.length) return [];
    const r = seed((sd || 1) * 7919 + 13), idx = points.map((_, i) => i);
    for (let i = idx.length - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); const v = idx[i]; idx[i] = idx[j]; idx[j] = v; }
    return Array.from({ length: n }, (_, i) => points[idx[i % idx.length]].slice());
  }
  // a star path: n spikes, outer / inner radius, rotated by rot (rad)
  function star(cx, cy, n, ro, ri, rot) {
    let d = "";
    for (let i = 0; i < n * 2; i++) {
      const a = rot + (i * Math.PI) / n, rr = i % 2 ? ri : ro;
      d += (i ? "L" : "M") + (cx + Math.cos(a) * rr).toFixed(1) + " " + (cy + Math.sin(a) * rr).toFixed(1);
    }
    return d + "Z";
  }
  // kinetic-word's beats (local s): the word lands 1 s after its start (index.json "impact": 1.0; a shorter span than
  // 2.5 s compresses everything by k) or on P.hit_at (a "hit" anchor on the spoken word) — then the 1 s build-up (pre,
  // shorter when the anchor is close to the start) runs from t0 = land - pre; the shatter takes the last 0.48·k s
  function kineticBeats(o) {
    const at = o.at || 0, end = Math.max(at + 1.2, o.end || at + 3.5), k = Math.min(1, (end - at) / 2.5);
    let land = at + k;
    if (typeof o.hit_at === "number" && isFinite(o.hit_at)) land = Math.min(Math.max(o.hit_at, at + 0.6 * k), end - k);
    const pre = Math.min(k, land - at);
    return { at, end, k, land, pre, t0: land - pre, shatter: end - 0.48 * k, dShat: 0.46 * k };
  }

  window.CutmateFX = { make, pure: { seed, trackAt, particleState, scrambleAt, openAmount, safeBox },
                       wow: { gridSize, gridStart, assignTargets, star, kineticBeats } };
  if (typeof module !== "undefined") module.exports = window.CutmateFX;
})();
