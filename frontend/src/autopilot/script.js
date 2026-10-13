/* The autopilot tour: a declarative list of steps. Each step switches to its tab and then drives it
   through the same API calls / bus events a person would trigger by hand. */
import { caption } from "../components/live/DemoStepper.jsx";

const shortPhase = (label) => (label || "").replace(/^Phase\s+\w+\s*-\s*/, "");

function liveNarration(gw) {
  const ev = gw.latest, phases = gw.meta?.demo_phases || [], i = gw.demo.index;
  if (!ev) return "Waiting for telemetry…";
  const phase = i != null && i < phases.length ? shortPhase(phases[i].label) + " · " : "";
  const floor = ev.decision.floor_clamped ? " 🛡 Safety floor holding: clinical PHI stays at Tier 3." : "";
  return `${phase}Tier ${ev.active_tier} (clinical Tier ${ev.clinical_tier}). ${caption(ev)}${floor}`;
}

const EPS_MIN = 0.05, EPS_MAX = 2;
const epsAt = (s) => +(EPS_MIN * (EPS_MAX / EPS_MIN) ** s).toFixed(3);

export const STEPS = [
  {
    id: "intro", tab: "overview", title: "Introduction", est: 5000,
    narration: "Agile-HQ-PQC picks the strongest quantum-safe encryption and privacy the network can afford, "
      + "and never lets raw patient data drop below Tier 3.",
    async run(x) { await x.wait(5000); },
  },
  {
    id: "live", tab: "live", title: "Heavy-load demo", est: 30000,
    narration: "Live control loop: we inject heavy network congestion and a CPU spike, then clear it.",
    async run(x) {
      await x.wait(1500);
      const gw = x.gw();
      if (gw.meta && !gw.meta.adaptive) {   // the demo shows adaptation, so make sure CADA is steering
        await x.api("/api/mode", { method: "POST", body: { adaptive: true, static_tier: 5 } });
        gw.setMeta((m) => ({ ...m, adaptive: true }));
      }
      await x.until(() => !x.gw().demo.active, 60000);   // a demo started by hand is still running
      x.gw().setDemo({ active: true, index: 0, startedAt: Date.now() });
      await x.api("/api/demo/start", { method: "POST" });
      await x.until(() => {
        const g = x.gw();
        x.say(liveNarration(g));
        return !g.demo.active && g.demo.index >= (g.meta?.demo_phases?.length || 0);
      }, 90000);
      x.say("Stress cleared. Hysteresis waits 3 calm cycles, then sessions re-key make-before-break back to Tier 5.");
      await x.until(() => x.gw().latest?.active_tier === 5, 15000);
      x.say("✓ Recovered to Tier 5. The clinical path never went below Tier 3.");
      await x.wait(3000);
    },
  },
  {
    id: "security", tab: "security", title: "Tamper Lab", est: 13000,
    narration: "Security Lab: an attacker flips a single bit in a live clinical packet.",
    async run(x) {
      await x.wait(2000);
      const attacks = [
        ["ciphertext", "Flip a bit in the ciphertext: the AEAD tag and the Ed25519 signature both fail."],
        ["tag", "Flip a bit in the authentication tag: the forged packet is rejected again."],
        ["signature", "Corrupt the Ed25519 signature: the packet signature check rejects it."],
      ];
      for (const [target, text] of attacks) {
        x.say(text);
        x.emit("security:tamper", { target, bit: 7 });
        await x.wait(3500);
      }
    },
  },
  {
    id: "privacy", tab: "privacy", title: "Privacy sliders", est: 14000,
    narration: "Privacy: lowering ε adds more Laplace noise to the ECG (stronger privacy, lower signal-to-noise).",
    async run(x) {
      await x.wait(1500);
      for (let i = 0; i <= 20; i++) { x.emit("privacy:eps", epsAt(1 - i / 20)); await x.wait(220); }
      x.emit("privacy:eps", 0.1);
      x.say("ε = 0.1 is the Tier 5 setting. Now raising K: every released record hides among at least K patients.");
      await x.wait(1500);
      for (const [k, l] of [[2, 2], [3, 2], [4, 2], [5, 3]]) { x.emit("privacy:kl", { k, l }); await x.wait(900); }
      x.say("K = 5, L = 3 is the Tier 5 setting: more information loss, much harder to re-identify a patient.");
      await x.wait(3000);
    },
  },
  {
    id: "results", tab: "results", title: "Evaluation results", est: 9000,
    narration: "Evidence from 30 paired trials: fewer SLA violations than static Tier 5 under stress, "
      + "65 % less cipher flapping with hysteresis, and the Tier 3 floor held in every trial.",
    async run(x) { await x.wait(9000); },
  },
];
