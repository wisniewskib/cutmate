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
    const [ex, ey] = o.emitter(t - age);
    const a2 = ang + (o.spin || 0) * age;
    return { x: ex + Math.cos(a2) * sp * age, y: ey + Math.sin(a2) * sp * age, alpha: 1 - age / life, size,
             color: (o.colors || ["#ffffff"])[Math.floor(r() * (o.colors || [1]).length)] };
  }

  function make(tl, root, cid, P) {
    const D = Math.max(0.001, P.dur || 1);
    const U = {};
    U.seed = seed;
    U.trackAt = trackAt;
    U.clock = function (fn) {
      const c = { t: 0 };
      tl.to(c, { t: D, duration: D, ease: "none", onUpdate: () => fn(c.t) }, 0);
      fn(0);
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
          composer = new EffectComposer(renderer);
          composer.addPass(new RenderPass(scene, camera));
          composer.addPass(new UnrealBloomPass(new THREE.Vector2(w, h), opt.bloom.strength ?? 1.5, opt.bloom.radius ?? 0.5, opt.bloom.threshold ?? 0));
          composer.addPass(new OutputPass());
          // alpha "luma" (default): the bloom blur writes alpha 1 everywhere, which would paint the frame black, so
          // rebuild alpha from brightness (premultiplied) and the glow composites like light (≈ screen) over the A-roll.
          // alpha "keep": skip that pass (solid objects keep their own alpha; dark parts stay opaque)
          if ((opt.bloom.alpha || "luma") !== "keep") {
            const { ShaderPass } = await import("three/addons/postprocessing/ShaderPass.js");
            composer.addPass(new ShaderPass({
              uniforms: { tDiffuse: { value: null } },
              vertexShader: "varying vec2 vUv; void main(){ vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0); }",
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
        return { THREE, scene, camera, renderer, composer, toWorld, render };
      })();
      window.__hf = window.__hf || {};
      window.__hf.buildReady = window.__hf.buildReady || {};
      window.__hf.buildReady[cid] = ready;
      return ready;
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
    U.anime = function (timeline) { U.clock((t) => timeline.seek(t * 1000)); return timeline; };
    U.lottie = function (anim) { U.clock((t) => anim.goToAndStop(t * 1000, false)); return anim; };
    return U;
  }

  window.CutmateFX = { make, pure: { seed, trackAt, particleState } };
  if (typeof module !== "undefined") module.exports = window.CutmateFX;
})();
