/** Play a short playful robot cheer (Web Audio — no asset files). */
export function playRobotCheer(): void {
  if (typeof window === "undefined") return;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  try {
    const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();

    const chirps: Array<{ freq: number; start: number; dur: number }> = [
      { freq: 520, start: 0, dur: 0.08 },
      { freq: 680, start: 0.09, dur: 0.08 },
      { freq: 840, start: 0.18, dur: 0.1 },
      { freq: 980, start: 0.3, dur: 0.12 },
      { freq: 720, start: 0.48, dur: 0.07 },
      { freq: 1100, start: 0.58, dur: 0.14 },
    ];

    const master = ctx.createGain();
    master.gain.value = 0.12;
    master.connect(ctx.destination);

    for (const chirp of chirps) {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "square";
      osc.frequency.value = chirp.freq;
      gain.gain.setValueAtTime(0, ctx.currentTime + chirp.start);
      gain.gain.linearRampToValueAtTime(1, ctx.currentTime + chirp.start + 0.01);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + chirp.start + chirp.dur);
      osc.connect(gain);
      gain.connect(master);
      osc.start(ctx.currentTime + chirp.start);
      osc.stop(ctx.currentTime + chirp.start + chirp.dur + 0.02);
    }

    window.setTimeout(() => {
      void ctx.close();
    }, 900);
  } catch {
    // Audio may be blocked; celebration still works visually.
  }
}
